"""Same-origin web application; anonymous, cookie-isolated demo workspaces."""
import os
import secrets
import threading
import time
from urllib.parse import urlsplit
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
import pipeline as p
import business

MODE = os.environ.get('PIPELINE_MODE', 'local')
if MODE not in {'local', 'kafka'}:
    raise RuntimeError('PIPELINE_MODE must be local or kafka')


def create_app():
    p.init_db()
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config['MAX_CONTENT_LENGTH'] = 8192

    @app.before_request
    def workspace():
        token = request.cookies.get('behavior_workspace', '')
        g.workspace = token if len(token) == 64 and all(c in '0123456789abcdef' for c in token) else secrets.token_hex(32)
        g.new_cookie = token != g.workspace
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            if origin and urlsplit(origin).netloc != request.host:
                return jsonify(error='Cross-origin writes are not allowed.'), 403
            if request.mimetype != 'application/json':
                return jsonify(error='Use application/json.'), 415

    @app.after_request
    def headers(response):
        if getattr(g, 'new_cookie', False):
            response.set_cookie('behavior_workspace', g.workspace, max_age=60*60*24*30,
                                httponly=True, secure=os.environ.get('COOKIE_SECURE') == '1', samesite='Strict')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.get('/')
    def landing():
        return send_from_directory(app.static_folder, 'landing.html')

    @app.get('/<page>')
    def page(page):
        names = {'playground': 'playground.html', 'architecture': 'architecture.html', 'insights': 'insights.html'}
        if page not in names:
            return jsonify(error='Page not found.'), 404
        return send_from_directory(app.static_folder, names[page])

    @app.get('/api/health')
    def health():
        with p.connect() as db:
            db.execute('SELECT 1')
            statuses = [dict(r) for r in db.execute('SELECT * FROM worker_status')]
        return jsonify(ok=True, mode=MODE, workers=statuses)

    @app.get('/api/catalog')
    def catalog():
        return jsonify(p.CONTENT)

    @app.get('/api/state')
    def state():
        return jsonify(p.snapshot(g.workspace))

    @app.get('/api/overview')
    def overview():
        source = request.args.get('source', 'all')
        if source not in {'all', 'real', 'simulated'}:
            return jsonify(error='Unknown source.'), 400
        return jsonify(p.overview(g.workspace, source))

    @app.get('/api/export')
    def export():
        # Export this workspace only, without the cookie that grants access to it.
        with p.connect() as db:
            events = [dict(r) for r in db.execute('SELECT * FROM events WHERE workspace=? ORDER BY seq', (g.workspace,))]
        for e in events:
            e.pop('workspace')
        return jsonify(schema_version=1, events=events)

    @app.post('/api/events')
    def events():
        try:
            eid = p.capture(g.workspace, request.get_json())
        except (ValueError, TypeError, AttributeError) as error:
            return jsonify(error=str(error)), 400
        if MODE == 'local':
            p.process_event(eid)
        return jsonify(p.snapshot(g.workspace))

    @app.get('/api/business')
    def business_state():
        return jsonify(business.report(g.workspace))

    @app.post('/api/business')
    def business_action():
        try:
            eid = business.execute(g.workspace, request.get_json())
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            return jsonify(error=str(error)), 400
        if MODE == 'local':
            p.process_event(eid)
        return jsonify(id=eid, business=business.report(g.workspace), state=p.snapshot(g.workspace))

    @app.post('/api/simulate')
    def simulate():
        created = p.seed(g.workspace)
        return jsonify(created=created, status='queued' if created else 'already_loaded'), 202 if created else 200

    @app.post('/api/reset')
    def reset():
        p.reset(g.workspace)
        return jsonify(p.snapshot(g.workspace))

    return app


def local_worker():
    while True:
        try:
            p.process_pending(24)
            p.heartbeat('local', 'running', 'Local processor; Kafka is not enabled.')
        except Exception as error:
            p.heartbeat('local', 'error', str(error)[:200])
        time.sleep(.2)


app = create_app()
if MODE == 'local' and os.environ.get('START_LOCAL_WORKER', '1') == '1':
    threading.Thread(target=local_worker, daemon=True).start()

if __name__ == '__main__':
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '8791')), threaded=True, debug=False)
