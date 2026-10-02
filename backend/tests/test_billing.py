import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest

from backend import app as module
from backend.tests.test_accounts import as_user, client, illustration, upload  # noqa: F401  (shared fixture)


def when(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat().replace('+00:00', 'Z')


def event(name, status, user_id='ana', ends_at=None, subscription='sub_1'):
    return {'meta': {'event_name': name, 'custom_data': {'user_id': user_id}},
            'data': {'type': 'subscriptions', 'id': subscription, 'attributes': {
                'status': status, 'customer_id': 42, 'renews_at': when(30), 'ends_at': ends_at,
                'urls': {'customer_portal': 'https://example.lemonsqueezy.com/billing'}}}}


def post(client, payload, secret='whsec', signature=None):
    raw = json.dumps(payload).encode()
    signature = signature or hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post('/api/billing/webhook', content=raw, headers={'X-Signature': signature})


@pytest.fixture
def webhook(monkeypatch):
    monkeypatch.setenv('LEMONSQUEEZY_WEBHOOK_SECRET', 'whsec')


def plan(client, user='ana'):
    return client.get('/api/me', headers=as_user(user)).json()['plan']['id']


def test_webhook_rejects_bad_signatures(client, webhook):
    assert post(client, event('subscription_created', 'active'), signature='nope').status_code == 401
    assert post(client, event('subscription_created', 'active'), secret='wrong').status_code == 401
    assert plan(client) == 'free'


def test_subscription_lifecycle(client, webhook):
    assert plan(client) == 'free'
    assert post(client, event('subscription_created', 'active')).status_code == 200
    me = client.get('/api/me', headers=as_user('ana')).json()
    assert me['plan']['id'] == 'pro' and me['usage']['limit'] == 200 and me['billing']['can_manage']
    # Cancelling keeps Pro until the paid period ends...
    post(client, event('subscription_cancelled', 'cancelled', ends_at=when(10)))
    assert plan(client) == 'pro'
    # ...then it lapses even if the "expired" event never arrives,
    with module.connect() as db:
        db.execute('UPDATE users SET plan_renews=? WHERE id=?', (when(-1), 'ana'))
    assert plan(client) == 'free'
    # and the expired event makes it official.
    post(client, event('subscription_expired', 'expired', ends_at=when(-1)))
    with module.connect() as db:
        assert db.execute("SELECT plan FROM users WHERE id='ana'").fetchone()[0] == 'free'


def test_later_events_find_the_user_by_subscription(client, webhook):
    post(client, event('subscription_created', 'active'))
    payload = event('subscription_updated', 'unpaid')
    payload['meta']['custom_data'] = None
    post(client, payload)
    assert plan(client) == 'free'


def test_payment_events_do_not_change_the_plan(client, webhook):
    assert post(client, event('subscription_payment_failed', 'expired')).status_code == 200
    assert post(client, {'meta': {'event_name': 'order_created'}, 'data': {}}).status_code == 200
    with module.connect() as db:
        assert db.execute("SELECT count(*) FROM users WHERE id='ana'").fetchone()[0] == 0


def test_checkout_needs_billing_setup(client, monkeypatch):
    for key in ('LEMONSQUEEZY_API_KEY', 'LEMONSQUEEZY_STORE_ID', 'LEMONSQUEEZY_PRO_VARIANT_ID'):
        monkeypatch.delenv(key, raising=False)
    assert client.post('/api/billing/checkout').status_code == 401
    assert client.post('/api/billing/checkout', headers=as_user('ana')).status_code == 503
    assert client.get('/api/billing/portal', headers=as_user('ana')).status_code == 404


def test_checkout_is_tagged_with_the_user(client, monkeypatch):
    monkeypatch.setenv('LEMONSQUEEZY_API_KEY', 'test-key')
    monkeypatch.setenv('LEMONSQUEEZY_STORE_ID', '1')
    monkeypatch.setenv('LEMONSQUEEZY_PRO_VARIANT_ID', '2')
    sent = {}

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {'data': {'attributes': {'url': 'https://example.lemonsqueezy.com/checkout/abc'}}}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, body=json)
        return Reply()

    monkeypatch.setattr(module.billing.httpx, 'post', fake_post)
    response = client.post('/api/billing/checkout', headers=as_user('ana'))
    assert response.json() == {'url': 'https://example.lemonsqueezy.com/checkout/abc'}
    assert sent['body']['data']['attributes']['checkout_data']['custom'] == {'user_id': 'ana'}
    assert sent['body']['data']['relationships']['variant']['data']['id'] == '2'


def test_library_examples_become_projects(client):
    library = client.get('/api/library').json()
    assert library['items'], 'run scripts/gallery/ingest.py'
    item = library['items'][0]
    project = client.post(f"/api/library/{item['id']}/use", headers=as_user('ana'))
    assert project.status_code == 201 and project.json()['name'] == item['title']
    assert client.post('/api/library/..%2F..%2Fetc/use', headers=as_user('ana')).status_code in (404, 405)
    assert client.post('/api/library/nope/use', headers=as_user('ana')).status_code == 404
    assert client.post(f"/api/library/{item['id']}/use").status_code == 401


def test_undetected_images_default_to_one_step_but_tutorial_examples_keep_their_grid(client):
    library = {item['id']: item for item in client.get('/api/library').json()['items']}
    for item_id, expected in (('objects-01-camera', (1, 1)), ('tutorial-04-rocket', (2, 2))):
        if item_id not in library:
            continue
        project = client.post(f'/api/library/{item_id}/use', headers=as_user('ana')).json()
        layout = client.get(f"/api/projects/{project['id']}/step-layout", headers=as_user('ana')).json()
        assert (layout['columns'], layout['rows']) == expected
        assert len(layout['crops']) == expected[0] * expected[1]


def test_yearly_checkout_uses_the_yearly_variant(client, monkeypatch):
    monkeypatch.setenv('LEMONSQUEEZY_API_KEY', 'test-key')
    monkeypatch.setenv('LEMONSQUEEZY_STORE_ID', '1')
    monkeypatch.setenv('LEMONSQUEEZY_PRO_VARIANT_ID', '2')
    monkeypatch.delenv('LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID', raising=False)
    sent = {}

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {'data': {'attributes': {'url': 'https://example.lemonsqueezy.com/checkout/yearly'}}}

    monkeypatch.setattr(module.billing.httpx, 'post', lambda url, headers, json, timeout: sent.update(body=json) or Reply())
    me = client.get('/api/me', headers=as_user('ana')).json()['billing']
    assert me['monthly'] == '$10' and me['yearly'] == '$84' and me['yearly_saving'] == 30 and not me['yearly_enabled']
    assert client.post('/api/billing/checkout', headers=as_user('ana'), json={'interval': 'year'}).status_code == 503
    monkeypatch.setenv('LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID', '3')
    assert client.get('/api/me', headers=as_user('ana')).json()['billing']['yearly_enabled']
    assert client.post('/api/billing/checkout', headers=as_user('ana'), json={'interval': 'year'}).status_code == 200
    assert sent['body']['data']['relationships']['variant']['data']['id'] == '3'
    assert client.post('/api/billing/checkout', headers=as_user('ana'), json={'interval': 'weekly'}).status_code == 422


def test_guests_can_try_but_not_export(client):
    guest = {'X-Dev-User': 'visitor', 'X-Dev-Guest': '1'}
    assert client.get('/api/me', headers=guest).json()['plan']['id'] == 'guest'
    # Browsing the sample and examples never uses up a guest's projects; the same example reopens the same copy.
    client.post('/api/sample', headers=guest)
    fox = [client.post('/api/library/animals-01-fox/use', headers=guest).json()['id'] for _ in range(3)]
    assert len(set(fox)) == 1
    assert client.post('/api/library/animals-00-cat/use', headers=guest).status_code == 201
    uploads = [client.post('/api/projects', headers=guest, files={'file': ('art.png', illustration(), 'image/png')}) for _ in range(4)]
    assert [r.status_code for r in uploads] == [201, 201, 201, 401]   # but only 3 of their own images
    project = uploads[0].json()
    exported = client.post(f"/api/projects/{project['id']}/jobs", headers=guest, json={})
    assert exported.status_code == 401 and 'free account' in exported.json()['detail']
    assert client.post('/api/billing/checkout', headers=guest).status_code == 401
    assert client.post('/api/images/clean-background', headers=guest, files={'file': ('a.png', b'x', 'image/png')}).status_code == 401
    # Signing in (same id, no longer anonymous) turns the guest into a Free user and keeps their projects.
    signed_in = {'X-Dev-User': 'visitor'}
    assert client.get('/api/me', headers=signed_in).json()['plan']['id'] == 'free'
    assert len(client.get('/api/projects', headers=signed_in).json()) == 6   # sample + 2 examples + 3 uploads
    assert client.post(f"/api/projects/{project['id']}/jobs", headers=signed_in, json={}).status_code == 202


def test_founding_member_offer(client, monkeypatch):
    for key, value in (('LEMONSQUEEZY_API_KEY', 'k'), ('LEMONSQUEEZY_STORE_ID', '1'), ('LEMONSQUEEZY_PRO_VARIANT_ID', '2'),
                       ('LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID', '3')):
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('STROKEBERRY_FOUNDER_CODE', raising=False)
    module.billing._offer_cache.update(at=0.0, value=None)
    assert client.get('/api/offer').json()['founder'] is None  # not switched on: nothing is shown or applied
    monkeypatch.setenv('STROKEBERRY_FOUNDER_CODE', 'FOUNDER')
    redeemed = {'total': 37}

    class Reply:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            pass

        def json(self):
            return self.body

    def fake_get(url, headers, timeout, params):
        if url.endswith('/discounts'):
            return Reply({'data': [{'id': '9', 'attributes': {'code': 'founder', 'max_redemptions': 100}}]})
        return Reply({'meta': {'page': {'total': redeemed['total']}}})

    sent = []
    monkeypatch.setattr(module.billing.httpx, 'get', fake_get)
    monkeypatch.setattr(module.billing.httpx, 'post', lambda url, headers, json, timeout: sent.append(json) or Reply(
        {'data': {'attributes': {'url': 'https://example.lemonsqueezy.com/checkout/x'}}}))
    module.billing._offer_cache.update(at=0.0, value=None)
    assert client.get('/api/offer').json()['founder'] == {'price': '$7', 'limit': 100, 'left': 63}
    assert client.get('/api/me', headers=as_user('ana')).json()['billing']['founder']['left'] == 63
    client.post('/api/billing/checkout', headers=as_user('ana'), json={'interval': 'month'})
    client.post('/api/billing/checkout', headers=as_user('ana'), json={'interval': 'year'})
    assert sent[0]['data']['attributes']['checkout_data']['discount_code'] == 'FOUNDER'
    assert 'discount_code' not in sent[1]['data']['attributes']['checkout_data']  # yearly is already discounted
    redeemed['total'] = 100  # sold out: the offer disappears and the code is no longer sent
    module.billing._offer_cache.update(at=0.0, value=None)
    assert client.get('/api/offer').json()['founder'] is None
    client.post('/api/billing/checkout', headers=as_user('ana'), json={'interval': 'month'})
    assert 'discount_code' not in sent[2]['data']['attributes']['checkout_data']


def make_pro(name):
    with module.connect() as db:
        db.execute("UPDATE users SET plan='pro' WHERE id=?", (name,))


def test_videos_over_a_minute_are_part_of_pro(client):
    project = upload(client, 'ana')
    url = f"/api/projects/{project['id']}/jobs"
    assert client.get('/api/me', headers=as_user('ana')).json()['plan']['max_duration'] == 60
    long = client.post(url, headers=as_user('ana'), json={'duration': 61})
    assert long.status_code == 403 and 'Pro' in long.json()['detail']
    assert client.post(url, headers=as_user('ana'), json={'duration': 60}).status_code == 202
    steps = {'stages': [{'crop': {'x': 0, 'y': 0, 'width': 1, 'height': 1}, 'label': 'All', 'seconds': 90}], 'align': True}
    assert client.post(f"/api/projects/{project['id']}/steps", headers=as_user('ana'), json=steps).status_code == 403
    make_pro('ana')
    with module.connect() as db:
        db.execute("UPDATE jobs SET status='completed'")
    assert client.get('/api/me', headers=as_user('ana')).json()['plan']['max_duration'] == 300
    assert client.post(url, headers=as_user('ana'), json={'duration': 300}).status_code == 202
    assert client.post(f"/api/projects/{project['id']}/steps", headers=as_user('ana'), json=steps).status_code == 201


def test_free_videos_come_back_a_month_after_they_were_made(client):
    from datetime import datetime, timedelta, timezone
    project = upload(client, 'ana')
    url = f"/api/projects/{project['id']}/jobs"
    now = datetime.now(timezone.utc)
    with module.connect() as db:
        for days_ago, name in ((10, 'a'), (20, 'b'), (5, 'c')):
            db.execute("INSERT INTO jobs (id, project_id, status, progress, stage, settings, created, user_id) VALUES (?,?,'completed',100,'',?,?,?)",
                       (name, project['id'], '{}', (now - timedelta(days=days_ago)).isoformat(), 'ana'))
    usage = client.get('/api/me', headers=as_user('ana')).json()['usage']
    assert usage['remaining'] == 0 and usage['resets']
    back = datetime.fromisoformat(usage['resets'])
    assert abs((back - (now + timedelta(days=10))).total_seconds()) < 5  # the 20-day-old video turns a month old in 10 days
    blocked = client.post(url, headers=as_user('ana'), json={})
    assert blocked.status_code == 402 and 'come back on' in blocked.json()['detail'] and 'Pro' in blocked.json()['detail']
    # once the oldest video is more than a month old it stops counting and the slot returns
    with module.connect() as db:
        db.execute("UPDATE jobs SET created=? WHERE id='b'", ((now - timedelta(days=31)).isoformat(),))
    assert client.get('/api/me', headers=as_user('ana')).json()['usage'] == {'used': 2, 'limit': 3, 'remaining': 1, 'period_days': 30, 'resets': None}
    assert client.post(url, headers=as_user('ana'), json={}).status_code == 202
