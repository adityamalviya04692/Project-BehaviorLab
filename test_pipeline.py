import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch
os.environ['START_LOCAL_WORKER'] = '0'
import pipeline as p
import server
import worker


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_db = p.DB
        p.DB = Path(self.tmp.name) / 'events.db'
        p.init_db()
        self.workspace = 'a' * 64
        self.app = server.create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        p.DB = self.original_db
        self.tmp.cleanup()

    def event(self, typ='content_view', cid='c1', eid=None, process=True):
        event_id = p.capture(self.workspace, {'id': eid or str(uuid.uuid4()), 'type': typ, 'content_id': cid, 'page': 'detail'})
        if process:
            p.process_event(event_id)
        return event_id

    def test_repeat_views_and_undo(self):
        for action in ['content_view', 'content_view', 'bookmark_add', 'bookmark_add', 'like_add']:
            self.event(action)
        self.assertEqual(p.snapshot(self.workspace)['scores']['Conferences'], 7)
        for action in ['bookmark_remove', 'bookmark_remove', 'like_remove']:
            self.event(action)
        self.assertEqual(p.snapshot(self.workspace)['scores']['Conferences'], 1)

    def test_idempotent_capture_and_processing(self):
        eid = self.event()
        self.event(eid=eid)
        p.process_event(eid)
        report = p.overview(self.workspace)
        self.assertEqual(report['totals']['captured'], 1)
        self.assertEqual(report['totals']['silver'], 1)
        self.assertEqual(report['users'][0]['scores']['Conferences'], 1)

    def test_conflicting_id_rejected(self):
        eid = self.event()
        with self.assertRaises(ValueError):
            self.event('bookmark_add', eid=eid)

    def test_capture_and_outbox_are_atomic(self):
        eid = self.event(process=False)
        with p.connect() as db:
            self.assertEqual(db.execute('SELECT topic FROM outbox WHERE event_id=?', (eid,)).fetchone()[0], 'behavior.conferences')
            self.assertEqual(db.execute('SELECT count(*) FROM silver').fetchone()[0], 0)
        self.assertEqual(p.snapshot(self.workspace)['pending'], 1)

    def test_out_of_order_consumption_replays_capture_sequence(self):
        added = self.event('bookmark_add', process=False)
        removed = self.event('bookmark_remove', process=False)
        p.process_event(removed, 'kafka')
        p.process_event(added, 'kafka')
        state = p.snapshot(self.workspace)
        self.assertEqual(state['scores']['Conferences'], 0)
        self.assertEqual(state['saved'], [])
        self.assertEqual([e['weight'] for e in state['events']], [4, -4])

    def test_recommendations_follow_interest(self):
        self.event('bookmark_add', 'c2')
        self.assertEqual(p.snapshot(self.workspace)['recommendations'][0], 'c6')

    def test_seed_is_bounded_isolated_and_idempotent(self):
        self.assertEqual(p.seed(self.workspace), 60)
        self.assertEqual(p.seed(self.workspace), 0)
        self.assertEqual(len(p.overview(self.workspace)['users']), 60)
        self.assertEqual(p.overview('b'*64)['totals']['captured'], 0)
        while p.process_pending():
            pass
        report = p.overview(self.workspace, 'simulated')
        self.assertGreater(report['totals']['captured'], 180)
        self.assertEqual(report['gold_count'], 60)
        self.assertEqual(report['totals']['captured'], report['totals']['silver'])
        self.assertEqual(p.overview(self.workspace, 'real')['totals']['captured'], 0)

    def test_reset_removes_layers_and_late_delivery_cannot_resurrect(self):
        eid = self.event()
        p.reset(self.workspace)
        p.process_event(eid, 'kafka')
        with p.connect() as db:
            for table in ['users', 'events', 'outbox', 'bronze', 'silver', 'gold']:
                self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0], 0)

    def test_api_validates_and_keeps_workspaces_private(self):
        data = {'id': str(uuid.uuid4()), 'type': 'bookmark_add', 'content_id': 'c1', 'page': 'detail'}
        self.assertEqual(self.client.post('/api/events', json=data).status_code, 200)
        self.assertEqual(len(self.client.get('/api/state').json['events']), 1)
        other = self.app.test_client()
        self.assertEqual(other.get('/api/state').json['events'], [])
        self.assertEqual(other.get('/api/overview').json['totals']['captured'], 0)
        exported = self.client.get('/api/export').json
        self.assertNotIn('workspace', exported['events'][0])
        self.assertNotIn('workspace', self.client.get('/api/state').json['events'][0])
        for bad in [None, [], {'id': []}, {**data, 'type': 'unknown'}, {**data, 'content_id': '<script>'}, {**data, 'source': 'simulated', 'page': 'unknown'}]:
            response = self.client.post('/api/events', data=json.dumps(bad), content_type='application/json')
            self.assertEqual(response.status_code, 400)

    def test_event_source_cannot_be_spoofed(self):
        data = {'id': str(uuid.uuid4()), 'type': 'content_view', 'content_id': 'c1', 'page': 'detail', 'source': 'simulated'}
        response = self.client.post('/api/events', json=data)
        self.assertEqual(response.json['events'][0]['source'], 'real')

    def test_navigation_filter_capture_and_input_guards(self):
        data = {'id': str(uuid.uuid4()), 'type': 'topic_filter', 'page': 'explore', 'filter_value': 'Shows'}
        r = self.client.post('/api/events', json=data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['total'], 0)
        self.assertEqual(r.json['events'][0]['filter_value'], 'Shows')
        self.assertEqual(self.client.post('/api/events', json=data, headers={'Origin':'https://malicious.test'}).status_code, 403)
        self.assertEqual(self.client.post('/api/events', data='hello').status_code, 415)
        self.assertEqual(self.client.post('/api/events', data='x'*9000, content_type='application/json').status_code, 413)

    def test_all_pages_and_assets(self):
        for route in ['/', '/playground', '/architecture', '/insights', '/static/landing.js', '/static/site.css']:
            r = self.client.get(route)
            self.assertEqual(r.status_code, 200, route)
            r.close()
        self.assertEqual(self.client.get('/unknown').status_code, 404)
        self.assertEqual(self.client.get('/api/overview?source=bad').status_code, 400)

    def test_publisher_only_marks_acknowledged_delivery(self):
        eid = self.event(process=False)
        message = Mock()
        message.partition.return_value = 2
        message.offset.return_value = 19
        worker.delivered(eid, 'offline', message)
        with p.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM outbox').fetchone()[0], 'pending')
        worker.delivered(eid, None, message)
        with p.connect() as db:
            row = db.execute('SELECT * FROM outbox').fetchone()
            self.assertEqual((row['status'], row['partition_id'], row['broker_offset']), ('published', 2, 19))

    def test_kafka_payload_excludes_workspace_capability(self):
        self.event(process=False)
        producer = Mock()
        producer.flush.return_value = 0
        worker.publish_batch(producer)
        payload = json.loads(producer.produce.call_args.kwargs['value'])
        self.assertNotIn('workspace', payload)
        self.assertEqual(payload['event_type'], 'content_view')

    def test_consumer_commit_after_success_and_not_after_failure(self):
        eid = self.event(process=False)
        with p.connect() as db:
            user_id = db.execute('SELECT user_id FROM events').fetchone()[0]
        message, consumer = Mock(), Mock()
        message.error.return_value = None
        message.value.return_value = json.dumps({'event_id': eid, 'schema_version': 1}).encode()
        message.topic.return_value = 'behavior.conferences'
        message.key.return_value = user_id.encode()
        with patch('worker.p.process_event', side_effect=RuntimeError('database unavailable')):
            with self.assertRaises(RuntimeError):
                worker.consume_message(consumer, message)
        consumer.commit.assert_not_called()
        worker.consume_message(consumer, message)
        consumer.commit.assert_called_once_with(message=message, asynchronous=False)
        self.assertEqual(p.snapshot(self.workspace)['scores']['Conferences'], 1)

    def test_publisher_failure_does_not_report_success(self):
        self.event(process=False)
        producer = Mock()
        def produce(*args, **kwargs):
            kwargs['on_delivery']('delivery failed', Mock())
        producer.produce.side_effect = produce
        producer.flush.return_value = 0
        with self.assertRaises(RuntimeError):
            worker.publish_batch(producer)
        with p.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM outbox').fetchone()[0], 'pending')

    def test_invalid_kafka_envelope_is_quarantined(self):
        message, consumer = Mock(), Mock()
        message.error.return_value = None
        message.value.return_value = b'invalid'
        message.topic.return_value = 'behavior.conferences'
        message.partition.return_value = 0
        message.offset.return_value = 10
        worker.consume_message(consumer, message)
        consumer.commit.assert_called_once()
        with p.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM dead_letters').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
