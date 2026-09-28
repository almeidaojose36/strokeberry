import io
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend import accounts
from backend import app as module


def illustration():
    image = Image.new('RGB', (240, 180), 'white')
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 30, 200, 150), outline='black', width=5, fill=(236, 45, 52))
    data = io.BytesIO()
    image.save(data, format='PNG')
    return data.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'DATA', tmp_path)
    monkeypatch.setattr(module, 'DB', tmp_path / 'test.sqlite')
    monkeypatch.setenv('STROKEBERRY_AUTH', 'dev')
    monkeypatch.delenv('FIREBASE_PROJECT_ID', raising=False)
    monkeypatch.setenv('STROKEBERRY_SECRET', 'test-secret')
    submitted = []
    monkeypatch.setattr(module.executor, 'submit', lambda *args: submitted.append(args))
    module.init_db()
    test_client = TestClient(module.app)
    test_client.submitted = submitted
    return test_client


def as_user(name):
    return {'X-Dev-User': name}


def upload(client, user):
    response = client.post('/api/projects', headers=as_user(user),
                           files={'file': ('art.png', illustration(), 'image/png')})
    assert response.status_code == 201
    return response.json()


def test_sign_in_is_required(client):
    assert client.get('/api/me').status_code == 401
    assert client.get('/api/projects').status_code == 401
    me = client.get('/api/me', headers=as_user('ana')).json()
    assert me['plan']['id'] == 'free'
    assert me['usage'] == {'used': 0, 'limit': 3, 'remaining': 3, 'period_days': None}


def test_users_only_see_their_own_work(client):
    project = upload(client, 'ana')
    assert [p['id'] for p in client.get('/api/projects', headers=as_user('ana')).json()] == [project['id']]
    assert client.get('/api/projects', headers=as_user('ben')).json() == []
    assert client.get(f"/api/projects/{project['id']}", headers=as_user('ben')).status_code == 404
    assert client.post(f"/api/projects/{project['id']}/jobs", headers=as_user('ben'), json={}).status_code == 404
    job = client.post(f"/api/projects/{project['id']}/jobs", headers=as_user('ana'), json={}).json()
    assert client.get(f"/api/jobs/{job['id']}", headers=as_user('ben')).status_code == 404
    assert client.get('/api/jobs', headers=as_user('ben')).json() == []


def test_media_links_need_a_valid_signature(client):
    project = upload(client, 'ana')
    assert '?e=' in project['source']
    assert client.get(project['source']).status_code == 200  # signed URL works without a header
    bare = project['source'].split('?')[0]
    assert client.get(bare).status_code == 403
    tampered = project['source'].replace('source.png', 'reveal.png')
    assert client.get(tampered).status_code == 403
    expired = accounts.sign_url(module.DATA, bare, ttl=-10)
    assert client.get(expired).status_code == 403


def test_free_plan_limits_quality_and_watermark(client):
    project = upload(client, 'ana')
    url = f"/api/projects/{project['id']}/jobs"
    locked = client.post(url, headers=as_user('ana'), json={'resolution': '1080p'})
    assert locked.status_code == 403 and 'Pro' in locked.json()['detail']
    for _ in range(3):
        response = client.post(url, headers=as_user('ana'), json={'resolution': '720p'})
        assert response.status_code == 202, response.text
        with module.connect() as db:  # let the next export past the two-at-a-time rule
            db.execute("UPDATE jobs SET status='completed'")
    assert all(args[3]['watermark'] is True for args in client.submitted)
    over = client.post(url, headers=as_user('ana'), json={})
    assert over.status_code == 402
    assert client.get('/api/me', headers=as_user('ana')).json()['usage']['remaining'] == 0


def test_pro_plan_gets_1080p_without_watermark(client):
    project = upload(client, 'pat')
    with module.connect() as db:
        db.execute("UPDATE users SET plan='pro' WHERE id='pat'")
    response = client.post(f"/api/projects/{project['id']}/jobs", headers=as_user('pat'), json={'resolution': '1080p'})
    assert response.status_code == 202
    assert client.submitted[-1][3]['watermark'] is False
    assert client.submitted[-1][3]['resolution'] == '1080p'


def test_failed_exports_do_not_use_up_the_allowance(client):
    project = upload(client, 'ana')
    client.post(f"/api/projects/{project['id']}/jobs", headers=as_user('ana'), json={})
    with module.connect() as db:
        db.execute("UPDATE jobs SET status='failed'")
    assert client.get('/api/me', headers=as_user('ana')).json()['usage']['used'] == 0


def test_firebase_tokens_are_verified(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public.update(kid='k1', alg='RS256', use='sig')
    monkeypatch.setenv('FIREBASE_PROJECT_ID', 'strokeberry-test')
    monkeypatch.setattr(accounts, '_firebase_keys', lambda force=False: {'k1': public})

    def token(**overrides):
        claims = {'sub': 'uid-1', 'email': 'ana@example.com', 'aud': 'strokeberry-test',
                  'iss': 'https://securetoken.google.com/strokeberry-test',
                  'iat': int(time.time()), 'exp': int(time.time()) + 600}
        claims.update(overrides)
        return jwt.encode(claims, key, algorithm='RS256', headers={'kid': 'k1'})

    assert accounts.verify_firebase_token(token())['sub'] == 'uid-1'
    for bad in (token(aud='someone-else'), token(exp=int(time.time()) - 600),
                token(iss='https://example.com'), token()[:-4] + 'abcd'):
        with pytest.raises(Exception) as error:
            accounts.verify_firebase_token(bad)
        assert getattr(error.value, 'status_code', None) == 401
