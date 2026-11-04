"""Runs against the live Compose deployment, including Kafka and materialization."""
import http.cookiejar
import json
import os
import time
import urllib.request
import uuid

base = os.environ.get('BASE_URL', 'http://127.0.0.1:8791')
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def call(path, data=None):
    request = urllib.request.Request(base+path, data=json.dumps(data).encode() if data is not None else None,
                                     headers={'Content-Type': 'application/json'})
    with client.open(request, timeout=15) as response:
        return json.load(response)

assert call('/api/health')['mode'] == 'kafka'
event = {'id': str(uuid.uuid4()), 'type': 'bookmark_add', 'content_id': 'c2', 'page': 'detail'}
call('/api/events', event)
call('/api/events', event)
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    state = call('/api/state')
    report = call('/api/overview')
    if state['scores']['Travel'] == 4 and report['totals']['published'] == 1:
        break
    time.sleep(1)
else:
    raise AssertionError('Kafka failed to publish and materialize within 90 seconds')
assert report['totals']['captured'] == report['totals']['silver'] == 1
assert report['recent'][0]['transport'] == 'kafka'
assert report['recent'][0]['partition_id'] is not None
assert report['recent'][0]['broker_offset'] is not None
call('/api/reset', {})
print('Live Kafka smoke passed: capture, duplicate retry, broker ack, consumer materialization and reset.')
