import json
import uuid
from datetime import date
import pipeline as p

PRODUCTS = {'kit': ('Conference notebook', 2400), 'tote': ('Northline tote', 3200), 'meal': ('Networking lunch', 4500)}
SLOTS = ['2026-12-01 10:00 ET', '2026-12-02 14:00 ET', '2026-12-03 11:30 ET']
ACTIONS = {'checkout_started', 'ticket_purchase', 'product_purchase', 'meeting_booked', 'event_brief_created', 'proposal_requested', 'ticket_checkin'}


def init_schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS business_records (
        id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
        user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        event_id TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL)""")


def record(db, workspace, user, source, action, event, payload, key=None):
    key = key or str(uuid.uuid4())
    p.insert_event(db, workspace, user, source, (key, action, event, {
        'ticket_purchase': 'checkout', 'product_purchase': 'checkout',
        'meeting_booked': 'meetings', 'event_brief_created': 'organize',
        'proposal_requested': 'brief', 'ticket_checkin': 'ticket',
        'checkout_started': 'checkout',
    }[action], None), payload)
    db.execute('INSERT INTO business_records VALUES(?,?,?,?,?)',
               (key, user, event, action, json.dumps(payload)))
    return key


def rows(db, workspace, source='all'):
    return [{**dict(r), **json.loads(r['payload'])} for r in db.execute(
        """SELECT b.id,b.user_id,b.event_id,b.action,b.payload,u.alias,u.source
           FROM business_records b JOIN users u USING(user_id)
           WHERE u.workspace=? AND (?='all' OR u.source=?) ORDER BY b.rowid""",
        (workspace, source, source))]


def execute(workspace, data):
    action, event = data['action'], data['event']
    key = str(uuid.UUID(data['id']))
    if action not in ACTIONS or event not in p.BY_ID:
        raise ValueError('Unknown event or action.')
    with p.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        user = p.user_for(db, workspace)
        records = rows(db, workspace)
        existing = next((r for r in records if r['id'] == key), None)
        if existing:
            if (existing['user_id'], existing['action'], existing['event_id']) != (user, action, event):
                raise ValueError('Request ID already used.')
            return key
        if len(records) >= 1500:
            raise ValueError('Workspace record limit reached.')
        payload = {}
        if action in {'ticket_purchase', 'product_purchase'}:
            quantity = data['quantity']
            if type(quantity) is not int or not 1 <= quantity <= 10:
                raise ValueError('Choose a quantity from 1 to 10.')
            item = data.get('item', 'ticket')
            if action == 'ticket_purchase':
                sold = sum(r['quantity'] for r in records if r['event_id'] == event and r['action'] == action)
                if sold + quantity > p.BY_ID[event]['capacity']:
                    raise ValueError('There are too few seats left.')
                name, price = 'General admission', p.BY_ID[event]['price_cents']
                item = 'ticket'
            else:
                name, price = PRODUCTS[item]
            payload = dict(item=item, name=name, quantity=quantity, total_cents=price*quantity)
        elif action == 'meeting_booked':
            slot = data['slot']
            if slot not in SLOTS or any(r.get('slot') == slot for r in records):
                raise ValueError('Choose another meeting slot.')
            payload = {'slot': slot}
        elif action == 'event_brief_created':
            title, city = data['title'].strip(), data['city'].strip()
            guests = data['guests']
            if not 1 <= len(title) <= 100 or not 1 <= len(city) <= 60 or type(guests) is not int or not 1 <= guests <= 5000:
                raise ValueError('Enter an event name, city and guest count.')
            requirements = data['requirements']
            if not isinstance(requirements, dict) or len(requirements) > 12 or any(
                not isinstance(k,str) or not isinstance(v,str) or len(k)>60 or len(v)>300 for k,v in requirements.items()):
                raise ValueError('Review your requirements.')
            payload = dict(title=title,city=city,guests=guests,date=date.fromisoformat(data['date']).isoformat(),requirements=requirements)
        elif action in {'ticket_checkin', 'proposal_requested'}:
            parent = data['record']
            expected = 'ticket_purchase' if action == 'ticket_checkin' else 'event_brief_created'
            original = next((r for r in records if r['id']==parent and r['user_id']==user and r['action']==expected and r['event_id']==event), None)
            if not original:
                raise ValueError('Record unavailable.')
            index = data.get('index', 1)
            if type(index) is not int or not 1 <= index <= original.get('quantity',1):
                raise ValueError('Invalid ticket.')
            if any(r['action']==action and r.get('record')==parent and r.get('index')==index for r in records):
                raise ValueError('Already recorded.')
            payload = dict(record=parent,index=index)
        return record(db, workspace, user, 'real', action, event, payload, key)


def seed_visitor(db, workspace, user, index):
    event = p.CONTENT[index % len(p.CONTENT)]
    cid = event['id']
    if index % 5 != 0:
        order = record(db, workspace, user, 'simulated', 'ticket_purchase', cid,
                       dict(item='ticket', name='General admission', quantity=1, total_cents=event['price_cents']))
        if index % 3 != 0:
            record(db, workspace, user, 'simulated', 'ticket_checkin', cid, dict(record=order,index=1))
    if index % 3 == 0:
        item = list(PRODUCTS)[index % 7 % len(PRODUCTS)]
        name, price = PRODUCTS[item]
        record(db, workspace, user, 'simulated', 'product_purchase', cid,
               dict(item=item,name=name,quantity=1,total_cents=price))


def report(workspace, source='all'):
    with p.connect() as db:
        records = rows(db, workspace, source)
    for r in records:
        r.pop('payload')
    return dict(records=records, products=PRODUCTS, slots=SLOTS,
                revenue_cents=sum(r.get('total_cents',0) for r in records))
