"""Kafka outbox publisher + materializing consumer. Run separately from the web server."""
import json
import os
import threading
import time
import uuid
from confluent_kafka import Consumer, Producer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
import pipeline as p


def config():
    values = {'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')}
    if os.environ.get('KAFKA_SECURITY_PROTOCOL'):
        values['security.protocol'] = os.environ['KAFKA_SECURITY_PROTOCOL']
    for env, key in [('KAFKA_SASL_MECHANISM', 'sasl.mechanism'), ('KAFKA_SASL_USERNAME', 'sasl.username'), ('KAFKA_SASL_PASSWORD', 'sasl.password')]:
        if os.environ.get(env):
            values[key] = os.environ[env]
    return values


def setup_topics():
    admin = AdminClient(config())
    futures = admin.create_topics([NewTopic(t, num_partitions=3, replication_factor=int(os.environ.get('KAFKA_REPLICATION_FACTOR', '1'))) for t in p.STREAMS], request_timeout=15)
    for future in futures.values():
        try:
            future.result()
        except KafkaException as error:
            if error.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
                raise


def delivered(eid, error, message):
    if error:
        p.heartbeat('publisher', 'retrying', 'Broker delivery failed; event retained in outbox.')
        return
    with p.connect() as db:
        db.execute("UPDATE outbox SET status='published',partition_id=?,broker_offset=?,published_at=? WHERE event_id=?",
                   (message.partition(), message.offset(), p.now(), eid))


def publish_batch(producer):
    with p.connect() as db:
        rows = db.execute("SELECT e.*,o.topic FROM events e JOIN outbox o USING(event_id) WHERE o.status='pending' ORDER BY e.seq LIMIT 100").fetchall()
    failures = []
    def acknowledge(eid, error, msg):
        delivered(eid, error, msg)
        if error:
            failures.append(eid)
    for event in rows:
        # Publish the full public event; keep the private workspace capability out of Kafka.
        payload = {k: event[k] for k in event.keys() if k not in {'workspace', 'topic'}}
        producer.produce(event['topic'], key=event['user_id'], value=json.dumps(payload),
                         on_delivery=lambda error, msg, eid=event['event_id']: acknowledge(eid, error, msg))
    remaining = producer.flush(12)
    if remaining or failures:
        raise RuntimeError('Broker timeout; unpublished events remain queued.')
    return len(rows)


def publisher():
    producer = Producer({**config(), 'enable.idempotence': True, 'acks': 'all', 'delivery.timeout.ms': 10000})
    while True:
        try:
            publish_batch(producer)
            p.heartbeat('publisher', 'running', 'Outbox delivery acknowledgments enabled.')
        except Exception:
            p.heartbeat('publisher', 'retrying', 'Broker unavailable; durable outbox will retry.')
        time.sleep(.5)


def consume_message(consumer, message):
    if message.error():
        raise KafkaException(message.error())
    try:
        data = json.loads(message.value())
        if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('event_id'), str):
            raise ValueError('Unsupported event envelope.')
        uuid.UUID(data['event_id'])
        with p.connect() as db:
            row = db.execute('SELECT o.topic,e.user_id FROM outbox o JOIN events e USING(event_id) WHERE e.event_id=?', (data['event_id'],)).fetchone()
        if row and (row['topic'] != message.topic() or message.key() != row['user_id'].encode()):
            raise ValueError('Topic or partition key does not match captured event.')
    except (ValueError, TypeError, UnicodeDecodeError):
        with p.connect() as db:
            db.execute('INSERT INTO dead_letters(topic,partition_id,broker_offset,error,created_at) VALUES(?,?,?,?,?)',
                       (message.topic(), message.partition(), message.offset(), 'Invalid event envelope; quarantined.', p.now()))
        consumer.commit(message=message, asynchronous=False)
        return
    p.process_event(data['event_id'], 'kafka')
    # A crash after DB commit but before offset commit replays safely by event_id.
    consumer.commit(message=message, asynchronous=False)


def consume():
    consumer = Consumer({**config(), 'group.id': os.environ.get('KAFKA_GROUP_ID', 'behavior-lab-events-v1'),
                         'auto.offset.reset': 'earliest', 'enable.auto.commit': False})
    consumer.subscribe(p.STREAMS)
    try:
        while True:
            msg = consumer.poll(1)
            if msg is not None:
                consume_message(consumer, msg)
            p.heartbeat('consumer', 'running', 'Offsets committed after database transaction.')
    finally:
        consumer.close()


def main():
    p.init_db()
    while True:
        try:
            setup_topics()
            break
        except Exception:
            p.heartbeat('publisher', 'retrying', 'Waiting for Kafka topic initialization.')
            time.sleep(5)
    threading.Thread(target=publisher, daemon=True).start()
    while True:
        try:
            consume()
        except Exception:
            p.heartbeat('consumer', 'retrying', 'Processing interrupted; restarting from committed offsets.')
            time.sleep(3)


if __name__ == '__main__':
    main()
