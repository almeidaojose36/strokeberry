import io

import numpy as np
import pytest
from PIL import Image

from backend import app as module, mailer
from backend.tests.test_accounts import as_user, client, illustration, upload  # noqa: F401  (shared fixture)


def make_pro(name):
    with module.connect() as db:
        db.execute("UPDATE users SET plan='pro' WHERE id=?", (name,))


def test_projects_can_be_renamed_duplicated_and_deleted(client):
    project = upload(client, 'ana')
    url = f"/api/projects/{project['id']}"
    assert client.patch(url, headers=as_user('ana'), json={'name': '  My cat  '}).json()['name'] == 'My cat'
    assert client.patch(url, headers=as_user('ben'), json={'name': 'x'}).status_code == 404
    assert client.patch(url, headers=as_user('ana'), json={'name': ''}).status_code == 422
    copy = client.post(f'{url}/duplicate', headers=as_user('ana')).json()
    assert copy['id'] != project['id'] and copy['name'] == 'My cat copy'
    assert client.post(f'{url}/duplicate', headers=as_user('ben')).status_code == 404
    assert len(client.get('/api/projects', headers=as_user('ana')).json()) == 2
    # a project with a video still rendering can't be deleted; one without can
    client.post(f'{url}/jobs', headers=as_user('ana'), json={})
    assert client.delete(url, headers=as_user('ana')).status_code == 409
    with module.connect() as db:
        db.execute("UPDATE jobs SET status='completed'")
    assert client.delete(url, headers=as_user('ben')).status_code == 404
    assert client.delete(url, headers=as_user('ana')).status_code == 204
    assert [p['id'] for p in client.get('/api/projects', headers=as_user('ana')).json()] == [copy['id']]
    assert client.get('/api/jobs', headers=as_user('ana')).json() == []
    assert not (module.DATA / project['id']).exists()


def test_exports_can_be_deleted_when_finished(client):
    project = upload(client, 'ana')
    job = client.post(f"/api/projects/{project['id']}/jobs", headers=as_user('ana'), json={}).json()
    assert client.delete(f"/api/jobs/{job['id']}", headers=as_user('ana')).status_code == 409
    with module.connect() as db:
        db.execute("UPDATE jobs SET status='completed'")
    (module.DATA / project['id'] / f"{job['id']}.mp4").write_bytes(b'video')
    assert client.delete(f"/api/jobs/{job['id']}", headers=as_user('ben')).status_code == 404
    assert client.delete(f"/api/jobs/{job['id']}", headers=as_user('ana')).status_code == 204
    assert not (module.DATA / project['id'] / f"{job['id']}.mp4").exists()


def test_saved_styles_are_limited_by_plan(client):
    style = {'name': 'Reel ink', 'settings': {'style': 'ink', 'ratio': '9:16'}}
    assert client.post('/api/presets', headers={**as_user('gus'), 'X-Dev-Guest': '1'}, json=style).status_code == 401
    assert client.post('/api/presets', headers=as_user('ana'), json=style).status_code == 201
    assert client.post('/api/presets', headers=as_user('ana'), json={**style, 'settings': {'style': 'pencil'}}).status_code == 201  # same name = update
    other = client.post('/api/presets', headers=as_user('ana'), json={'name': 'Second', 'settings': {}})
    assert other.status_code == 402 and 'Pro' in other.json()['detail']
    saved = client.get('/api/presets', headers=as_user('ana')).json()
    assert len(saved) == 1 and saved[0]['settings']['style'] == 'pencil'
    assert client.get('/api/presets', headers=as_user('ben')).json() == []
    make_pro('ana')
    assert client.post('/api/presets', headers=as_user('ana'), json={'name': 'Second', 'settings': {}}).status_code == 201
    assert client.delete(f"/api/presets/{saved[0]['id']}", headers=as_user('ben')).status_code == 404
    assert client.delete(f"/api/presets/{saved[0]['id']}", headers=as_user('ana')).status_code == 204


def png(color):
    data = io.BytesIO()
    Image.new('RGBA', (300, 120), color).save(data, format='PNG')
    return data.getvalue()


def test_brand_kit_is_pro_only_and_shapes_exports(client):
    project = upload(client, 'ana')
    assert client.get('/api/brand', headers=as_user('ana')).json()['allowed'] is False
    assert client.put('/api/brand', headers=as_user('ana'), json={'ink_color': '#112233'}).status_code == 402
    make_pro('ana')
    assert client.put('/api/brand', headers=as_user('ana'), json={'ink_color': 'blue'}).status_code == 422
    kit = client.put('/api/brand', headers=as_user('ana'), json={'name': 'Little Crumb', 'ink_color': '#112233', 'logo_corner': 'top-left'}).json()
    assert kit['ink_color'] == '#112233' and kit['logo'] is None
    bad = client.post('/api/brand/logo', headers=as_user('ana'), files={'file': ('x.png', b'not an image', 'image/png')})
    assert bad.status_code == 400
    kit = client.post('/api/brand/logo', headers=as_user('ana'), files={'file': ('logo.png', png((200, 30, 30, 255)), 'image/png')}).json()
    assert kit['logo'] and client.get(kit['logo']).status_code == 200
    assert client.get(kit['logo'].split('?')[0]).status_code == 403  # the link is signed
    client.post(f"/api/projects/{project['id']}/jobs", headers=as_user('ana'), json={})
    settings = client.submitted[-1][3]
    assert settings['ink_color'] == '#112233' and settings['logo_corner'] == 'top-left' and settings['watermark'] is False
    # the server path is never sent to the browser
    assert 'logo' not in client.get('/api/jobs', headers=as_user('ana')).json()[0]['settings']
    client.put('/api/brand', headers=as_user('ana'), json={'ink_color': '#112233', 'enabled': False})
    with module.connect() as db:
        db.execute("UPDATE jobs SET status='completed'")
    client.post(f"/api/projects/{project['id']}/jobs", headers=as_user('ana'), json={})
    assert 'ink_color' not in client.submitted[-1][3]


def test_logo_is_blended_into_frames():
    from backend import watermark
    import tempfile, pathlib
    path = pathlib.Path(tempfile.mkdtemp()) / 'logo.png'
    path.write_bytes(png((255, 0, 0, 255)))
    canvas = np.full((540, 960, 3), 250, np.uint8)
    watermark.apply_logo(canvas, path, 'bottom-right')
    assert (canvas[-60:, -300:, 1] < 100).any() and (canvas[:60, :60] == 250).all()
    tall = np.full((960, 540, 3), 250, np.uint8)
    watermark.apply_logo(tall, path, 'bottom-right')  # 9:16 keeps clear of the bottom, so it moves to the top
    assert (tall[:120, -200:, 1] < 100).any()


def test_batch_export_is_pro_and_counts_every_video(client):
    a, b = upload(client, 'ana'), upload(client, 'ana')
    body = {'project_ids': [a['id'], b['id']], 'ratios': ['16:9', '9:16', '1:1'], 'settings': {'style': 'ink'}}
    assert client.post('/api/batch', headers=as_user('ana'), json=body).status_code == 402
    make_pro('ana')
    assert client.post('/api/batch', headers=as_user('ben'), json=body).status_code == 402  # Free
    made = client.post('/api/batch', headers=as_user('ana'), json=body)
    assert made.status_code == 202 and len(made.json()) == 6
    assert sorted(j['settings']['ratio'] for j in made.json()) == ['16:9'] * 2 + ['1:1'] * 2 + ['9:16'] * 2
    assert client.post('/api/batch', headers=as_user('ana'), json={**body, 'project_ids': ['nope']}).status_code == 404
    assert client.post('/api/batch', headers=as_user('ana'), json={**body, 'project_ids': [a['id']] * 7}).status_code == 422
    # Pro may queue up to nine at once; the fourth format-set goes over
    assert client.post('/api/batch', headers=as_user('ana'), json=body).status_code == 429


def test_batch_respects_the_monthly_allowance(client):
    project = upload(client, 'ana')
    make_pro('ana')
    with module.connect() as db:
        for i in range(199):
            db.execute("INSERT INTO jobs (id, project_id, status, progress, stage, settings, created, user_id) VALUES (?,?,'completed',100,'',?,?,?)",
                       (f'old{i}', project['id'], '{}', module.datetime.now(module.timezone.utc).isoformat(), 'ana'))
    body = {'project_ids': [project['id']], 'ratios': ['16:9', '9:16']}
    over = client.post('/api/batch', headers=as_user('ana'), json=body)
    assert over.status_code == 429 and 'limit' in over.json()['detail']
    assert client.post('/api/batch', headers=as_user('ana'), json={**body, 'ratios': ['16:9']}).status_code == 202


def test_weekly_ideas_are_stable_and_usable(client):
    ideas = client.get('/api/ideas').json()
    assert len(ideas) == 3 and all({'id', 'title', 'thumb', 'style', 'ratio', 'tip'} <= set(i) for i in ideas)
    assert ideas == client.get('/api/ideas').json()


def test_free_users_get_a_welcome_and_allowance_emails(client, monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, 'send', lambda to, subject, paragraphs, button=None: sent.append((to, subject)) or True)
    client.get('/api/me', headers=as_user('ana'))
    client.get('/api/me', headers=as_user('ana'))
    assert sent == [('ana@example.test', 'Welcome to Strokeberry')]  # once only
    project = upload(client, 'ana')
    for number in (1, 2, 3):
        job = client.post(f"/api/projects/{project['id']}/jobs", headers=as_user('ana'), json={}).json()
        module.notify_allowance(job['id'])
        with module.connect() as db:
            db.execute("UPDATE jobs SET status='completed'")
    subjects = [s for _, s in sent]
    assert subjects == ['Welcome to Strokeberry', 'You have 1 free video left', 'You’ve used your 3 free videos this month']
    module.notify_allowance(job['id'])
    assert len(sent) == 3  # never repeated
    # guests get nothing
    client.get('/api/me', headers={'X-Dev-User': 'g', 'X-Dev-Guest': '1'})
    assert len(sent) == 3


def test_emails_need_smtp_settings(monkeypatch):
    for key in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD'):
        monkeypatch.delenv(key, raising=False)
    assert mailer.welcome('a@example.com', 'Ana') is False
    started = []
    monkeypatch.setenv('SMTP_HOST', 'smtp.example.com')
    monkeypatch.setenv('SMTP_USER', 'hi@example.com')
    monkeypatch.setenv('SMTP_PASSWORD', 'secret')
    monkeypatch.setattr(mailer.threading, 'Thread', lambda target, args, daemon: type('T', (), {'start': lambda self: started.append(args)})())
    assert mailer.welcome('a@example.com', 'Ana Silva') is True
    to, subject, text, html = started[0]
    assert to == 'a@example.com' and 'Hi Ana,' in text and '/studio/' in html


def test_abandoned_guests_are_pruned_but_signed_in_users_are_not(client):
    from datetime import datetime, timedelta, timezone
    from backend import prune
    guest = {'X-Dev-User': 'old-guest', 'X-Dev-Guest': '1'}
    made = client.post('/api/library/animals-01-fox/use', headers=guest).json()
    upload(client, 'ana')
    long_ago = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    with module.connect() as db:
        db.execute('UPDATE users SET created=?', (long_ago,))  # everyone is old...
        assert prune.prune_guests(db, module.DATA) == 1          # ...but only the guest goes
        assert db.execute("SELECT count(*) FROM users WHERE id='ana'").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM projects WHERE user_id='old-guest'").fetchone()[0] == 0
    assert not (module.DATA / made['id']).exists()
    assert len(client.get('/api/projects', headers=as_user('ana')).json()) == 1


def test_a_new_visitors_simultaneous_requests_create_one_account_and_one_welcome(client, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    sent = []
    monkeypatch.setattr(mailer, 'send', lambda to, subject, paragraphs, button=None: sent.append(subject) or True)
    gate = threading.Barrier(8)

    def visit(_):
        gate.wait()
        return client.get('/api/me', headers=as_user('newcomer')).status_code

    with ThreadPoolExecutor(8) as pool:
        assert set(pool.map(visit, range(8))) == {200}
    with module.connect() as db:
        assert db.execute("SELECT count(*) FROM users WHERE id='newcomer'").fetchone()[0] == 1
    assert sent == ['Welcome to Strokeberry']


def test_missing_lines_are_suggested_and_only_added_when_accepted(client):
    import cv2
    from backend.tests.test_linework import unlined_patch_drawing
    ok, png = cv2.imencode('.png', cv2.cvtColor(unlined_patch_drawing(), cv2.COLOR_RGB2BGR))
    project = client.post('/api/projects', headers=as_user('ana'), files={'file': ('art.png', png.tobytes(), 'image/png')}).json()
    url = f"/api/projects/{project['id']}/enhance"
    assert project['enhance']['state'] is None and project['enhance']['count'] >= 1
    plain = project['strokes']
    assert client.post(url, headers=as_user('ben'), json={'accept': True}).status_code == 404
    accepted = client.post(url, headers=as_user('ana'), json={'accept': True}).json()
    assert accepted['enhance']['state'] == 'accepted' and accepted['strokes'] > plain
    declined = client.post(url, headers=as_user('ana'), json={'accept': False}).json()
    assert declined['enhance']['state'] == 'rejected' and declined['strokes'] == plain
    # artwork that is already fully outlined has nothing to suggest
    assert client.post(url.replace(project['id'], upload(client, 'ana')['id']), headers=as_user('ana'), json={'accept': True}).status_code == 409
