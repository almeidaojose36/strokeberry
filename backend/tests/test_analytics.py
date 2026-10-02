from fastapi.testclient import TestClient

from backend import analytics
from backend import app as app_module

BROWSER = {'user-agent': 'Mozilla/5.0 (Macintosh) Safari/605', 'accept': 'text/html'}


def events(name):
    with app_module.connect() as db:
        return db.execute('SELECT * FROM events WHERE name=?', (name,)).fetchall()


def test_page_views_are_counted_without_cookies_and_bots_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'DB', tmp_path / 'studio.sqlite')
    dist = app_module.ROOT / 'dist'
    if not (dist / 'index.html').exists():
        return  # the built site is needed to serve pages
    monkeypatch.delenv('FIREBASE_PROJECT_ID', raising=False)
    app_module.init_db()
    client = TestClient(app_module.app)  # no lifespan: it would load .env.local into the other tests
    response = client.get('/?utm_source=tiktok', headers=BROWSER)
    assert 'set-cookie' not in response.headers
    client.get('/', headers={**BROWSER, 'referer': 'https://www.youtube.com/watch?v=1'})
    client.get('/', headers={'user-agent': 'Googlebot/2.1', 'accept': 'text/html'})
    client.get('/favicon-32.png', headers=BROWSER)
    views = events('pageview')
    assert len(views) == 2
    assert {row['source'] for row in views} == {'tiktok', 'youtube.com'}
    assert views[0]['visitor'] == views[1]['visitor'] and len(views[0]['visitor']) == 16  # same browser, same day


def test_funnel_steps_and_report(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'DB', tmp_path / 'studio.sqlite')
    monkeypatch.setenv('STROKEBERRY_AUTH', 'dev')
    monkeypatch.delenv('FIREBASE_PROJECT_ID', raising=False)
    client = TestClient(app_module.app)
    headers = {'X-Dev-User': 'ana', **BROWSER}
    client.post('/api/sample', headers=headers)
    assert client.post('/api/event', json={'name': 'upgrade_open'}, headers=headers).status_code == 200
    client.post('/api/event', json={'name': 'made_up'}, headers=headers)
    assert [row['detail'] for row in events('project')] == ['example']
    assert len(events('upgrade_open')) == 1 and not events('made_up')
    with app_module.connect() as db:
        text = analytics.report(db, 7)
    assert 'Saw the upgrade offer' in text and 'Visitors per day' in text
