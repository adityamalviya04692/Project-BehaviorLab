"""Durable capture, inspectable processing layers, and deterministic profiles."""
import json
import os
import random
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
CONTENT = json.loads((ROOT / 'catalog.json').read_text())
BY_ID = {c['id']: c for c in CONTENT}
TOPICS = sorted({c['topic'] for c in CONTENT})
ACTIONS = {'content_view', 'bookmark_add', 'bookmark_remove', 'like_add', 'like_remove', 'page_view', 'topic_filter'}
PAGES = {'discover', 'explore', 'saved', 'profile', 'detail'}
STREAMS = ['behavior.' + t.lower() for t in TOPICS] + ['behavior.navigation']
DB = Path(os.environ.get('BEHAVIOR_DB', ROOT / 'data' / 'behavior.sqlite3'))


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          user_id TEXT PRIMARY KEY, workspace TEXT NOT NULL, alias TEXT NOT NULL,
          source TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS users_workspace ON users(workspace);
        CREATE TABLE IF NOT EXISTS events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
          workspace TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
          event_type TEXT NOT NULL, content_id TEXT, category TEXT, page TEXT NOT NULL,
          filter_value TEXT, source TEXT NOT NULL, received_at TEXT NOT NULL, schema_version INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS events_workspace ON events(workspace, seq);
        CREATE INDEX IF NOT EXISTS events_user ON events(user_id, seq);
        CREATE TABLE IF NOT EXISTS outbox (
          event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
          topic TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          partition_id INTEGER, broker_offset INTEGER, published_at TEXT);
        CREATE TABLE IF NOT EXISTS bronze (
          event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
          payload TEXT NOT NULL, ingested_at TEXT NOT NULL, transport TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS silver (
          event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
          user_id TEXT NOT NULL, category TEXT, effective_weight INTEGER NOT NULL DEFAULT 0,
          processed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS gold (
          user_id TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
          scores TEXT NOT NULL, saved TEXT NOT NULL, liked TEXT NOT NULL, viewed TEXT NOT NULL,
          updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS worker_status (
          name TEXT PRIMARY KEY, status TEXT NOT NULL, detail TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS dead_letters (
          id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT, partition_id INTEGER,
          broker_offset INTEGER, error TEXT, created_at TEXT);
        ''')


def user_for(db, workspace):
    row = db.execute("SELECT user_id FROM users WHERE workspace=? AND source='real'", (workspace,)).fetchone()
    if row:
        return row[0]
    uid = str(uuid.uuid4())
    db.execute('INSERT INTO users VALUES(?,?,?,?,?)', (uid, workspace, 'You', 'real', now()))
    return uid


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object.')
    eid = str(uuid.UUID(data.get('id', '')))
    typ = data.get('type')
    cid = data.get('content_id')
    page = data.get('page', 'discover')
    category_filter = data.get('filter_value')
    if not isinstance(typ, str) or typ not in ACTIONS or not isinstance(page, str) or page not in PAGES:
        raise ValueError('Unknown action or page.')
    if cid is not None and (not isinstance(cid, str) or cid not in BY_ID):
        raise ValueError('Unknown content.')
    if typ not in {'page_view', 'topic_filter'} and cid is None:
        raise ValueError('This action needs a content ID.')
    if typ in {'page_view', 'topic_filter'} and cid is not None:
        raise ValueError('Navigation must not include content.')
    if typ == 'topic_filter' and category_filter not in TOPICS + ['All']:
        raise ValueError('Unknown topic filter.')
    if typ != 'topic_filter' and category_filter is not None:
        raise ValueError('Unexpected filter value.')
    return eid, typ, cid, page, category_filter


def insert_event(db, workspace, uid, source, values):
    eid, typ, cid, page, category_filter = values
    existing = db.execute('SELECT * FROM events WHERE event_id=?', (eid,)).fetchone()
    if existing:
        if (existing['workspace'], existing['user_id'], existing['event_type'], existing['content_id'], existing['page'], existing['filter_value']) != (workspace, uid, typ, cid, page, category_filter):
            raise ValueError('Event ID already used for another action.')
        return eid
    category = BY_ID[cid]['topic'] if cid else None
    db.execute('''INSERT INTO events(event_id,workspace,user_id,event_type,content_id,category,page,
                  filter_value,source,received_at,schema_version) VALUES(?,?,?,?,?,?,?,?,?,?,1)''',
               (eid, workspace, uid, typ, cid, category, page, category_filter, source, now()))
    stream = 'behavior.' + (category.lower() if category else 'navigation')
    db.execute('INSERT INTO outbox(event_id,topic) VALUES(?,?)', (eid, stream))
    return eid


def capture(workspace, data):
    values = validate(data)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        uid = user_for(db, workspace)
        if db.execute('SELECT count(*) FROM events WHERE workspace=?', (workspace,)).fetchone()[0] >= 8000:
            raise ValueError('Demo limit reached. Start a new session to continue.')
        return insert_event(db, workspace, uid, 'real', values)


def fold(events):
    scores = dict.fromkeys(TOPICS, 0)
    saved, liked, viewed = set(), set(), set()
    weights = {}
    for e in events:
        cid, typ, delta = e['content_id'], e['event_type'], 0
        if cid:
            if typ == 'content_view' and cid not in viewed:
                viewed.add(cid)
                delta = 1
            for field, target, weight in [('bookmark', saved, 4), ('like', liked, 2)]:
                if typ == field + '_add' and cid not in target:
                    target.add(cid)
                    delta = weight
                elif typ == field + '_remove' and cid in target:
                    target.remove(cid)
                    delta = -weight
            scores[e['category']] += delta
        weights[e['event_id']] = delta
    return scores, saved, liked, viewed, weights


def process_event(eid, transport='local'):
    """Atomic materialization; replay by capture sequence also handles cross-topic arrival order."""
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        event = db.execute('SELECT * FROM events WHERE event_id=?', (eid,)).fetchone()
        if not event:  # The visitor may have explicitly reset their workspace.
            return
        if db.execute('SELECT 1 FROM silver WHERE event_id=?', (eid,)).fetchone():
            return
        db.execute('INSERT OR IGNORE INTO bronze VALUES(?,?,?,?)', (eid, json.dumps(dict(event)), now(), transport))
        db.execute('INSERT INTO silver(event_id,user_id,category,processed_at) VALUES(?,?,?,?)',
                   (eid, event['user_id'], event['category'], now()))
        events = db.execute('''SELECT e.* FROM events e JOIN silver s USING(event_id)
                               WHERE e.user_id=? ORDER BY e.seq''', (event['user_id'],)).fetchall()
        scores, saved, liked, viewed, weights = fold(events)
        db.executemany('UPDATE silver SET effective_weight=? WHERE event_id=?', [(w, k) for k, w in weights.items()])
        db.execute('INSERT OR REPLACE INTO gold VALUES(?,?,?,?,?,?)',
                   (event['user_id'], json.dumps(scores), json.dumps(sorted(saved)), json.dumps(sorted(liked)), json.dumps(sorted(viewed)), now()))
        if transport == 'local':
            db.execute("UPDATE outbox SET status='local',published_at=? WHERE event_id=?", (now(), eid))


def process_pending(limit=100):
    with connect() as db:
        rows = db.execute("SELECT event_id FROM outbox WHERE status='pending' ORDER BY rowid LIMIT ?", (limit,)).fetchall()
    for row in rows:
        process_event(row[0])
    return len(rows)


def heartbeat(name, status, detail):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO worker_status VALUES(?,?,?,?)', (name, status, detail, now()))


def seed(workspace, count=60):
    """A bounded synthetic cohort, isolated to this visitor's workspace."""
    rng = random.Random(41)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM users WHERE workspace=? AND source='simulated'", (workspace,)).fetchone():
            return 0
        for i in range(count):
            uid = str(uuid.uuid4())
            db.execute('INSERT INTO users VALUES(?,?,?,?,?)', (uid, workspace, f'Visitor {i+1:03}', 'simulated', now()))
            favored = TOPICS[i % len(TOPICS)]
            cards = [c for c in CONTENT if c['topic'] == favored]
            others = [c for c in CONTENT if c['topic'] != favored]
            for c in cards + rng.sample(others, 1):
                for action in ['content_view'] + (['bookmark_add'] if rng.random() < .55 else []) + (['like_add'] if rng.random() < .4 else []):
                    insert_event(db, workspace, uid, 'simulated', (str(uuid.uuid4()), action, c['id'], 'detail', None))
    return count


def snapshot(workspace):
    with connect() as db:
        uid = user_for(db, workspace)
        rows = db.execute('''SELECT e.*,s.effective_weight AS weight,o.topic AS stream,o.status,
          o.partition_id,o.broker_offset FROM events e JOIN outbox o USING(event_id)
          LEFT JOIN silver s USING(event_id) WHERE e.user_id=? ORDER BY e.seq''', (uid,)).fetchall()
        profile = db.execute('SELECT * FROM gold WHERE user_id=?', (uid,)).fetchone()
    scores = json.loads(profile['scores']) if profile else dict.fromkeys(TOPICS, 0)
    result = {'scores': scores, 'total': sum(scores.values()), 'user_id': uid}
    for name in ['saved', 'liked', 'viewed']:
        result[name] = json.loads(profile[name]) if profile else []
    result['events'] = [{**{k: e[k] for k in e.keys() if k != 'workspace'}, 'id': e['event_id'], 'type': e['event_type'], 'topic': e['category'],
                         'timestamp': e['received_at'], 'weight': e['weight'] or 0} for e in rows]
    result['pending'] = sum(e['weight'] is None for e in rows)
    ranked = sorted(CONTENT, key=lambda c: (scores[c['topic']], c['id'] not in result['viewed']), reverse=True)
    result['recommendations'] = [c['id'] for c in ranked if c['id'] not in result['saved']][:4]
    return result


def overview(workspace, source='all'):
    suffix = '' if source == 'all' else ' AND e.source=?'
    params = (workspace,) if source == 'all' else (workspace, source)
    with connect() as db:
        totals = dict(db.execute('''SELECT count(*) AS captured,
          count(b.event_id) AS bronze,count(s.event_id) AS silver,
          sum(CASE WHEN o.status='pending' THEN 1 ELSE 0 END) AS pending,
          sum(CASE WHEN o.status='published' THEN 1 ELSE 0 END) AS published,
          sum(CASE WHEN e.source='real' THEN 1 ELSE 0 END) AS real_events,
          sum(CASE WHEN e.source='simulated' THEN 1 ELSE 0 END) AS simulated_events
          FROM events e JOIN outbox o USING(event_id) LEFT JOIN bronze b USING(event_id)
          LEFT JOIN silver s USING(event_id) WHERE e.workspace=?''' + suffix, params).fetchone())
        streams = [dict(r) for r in db.execute('''SELECT o.topic,count(*) AS captured,
          sum(CASE WHEN o.status='published' THEN 1 ELSE 0 END) AS published,
          sum(CASE WHEN s.event_id IS NOT NULL THEN 1 ELSE 0 END) AS processed
          FROM events e JOIN outbox o USING(event_id) LEFT JOIN silver s USING(event_id)
          WHERE e.workspace=?''' + suffix + ' GROUP BY o.topic', params)]
        recent = [dict(r) for r in db.execute('''SELECT e.*,u.alias,o.topic AS stream,o.status,o.partition_id,o.broker_offset,
          s.effective_weight,b.transport FROM events e JOIN users u USING(user_id)
          JOIN outbox o USING(event_id) LEFT JOIN silver s USING(event_id) LEFT JOIN bronze b USING(event_id)
          WHERE e.workspace=?''' + suffix + ' ORDER BY e.seq DESC LIMIT 50', params)]
        users = [dict(r) for r in db.execute('''SELECT u.*,g.scores,g.saved,g.liked,g.viewed,g.updated_at
          FROM users u LEFT JOIN gold g USING(user_id) WHERE u.workspace=?''' +
          ('' if source == 'all' else ' AND u.source=?') + ' ORDER BY u.created_at', params)]
        statuses = [dict(r) for r in db.execute('SELECT * FROM worker_status')]
    for u in users:
        for field in ['scores', 'saved', 'liked', 'viewed']:
            u[field] = json.loads(u[field]) if u[field] else (dict.fromkeys(TOPICS, 0) if field == 'scores' else [])
        u.pop('workspace')
    for r in recent:
        r.pop('workspace')
    segments = []
    for topic in TOPICS:
        interested = [u for u in users if u['scores'][topic] > 0]
        intent = [u for u in users if any(BY_ID[c]['topic'] == topic for c in u['saved'])]
        segments.append({'topic': topic, 'interested': len(interested), 'high_intent': len(intent),
                         'points': sum(u['scores'][topic] for u in users)})
    return {'totals': {k: v or 0 for k, v in totals.items()}, 'streams': streams, 'recent': recent,
            'users': users, 'segments': segments, 'workers': statuses,
            'gold_count': sum(bool(u['updated_at']) for u in users),
            'bookmark_visitors': sum(bool(u['saved']) for u in users),
            'view_visitors': sum(bool(u['viewed']) for u in users), 'source': source}


def reset(workspace):
    with connect() as db:
        db.execute('DELETE FROM users WHERE workspace=?', (workspace,))
