import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest

from backend import app as module
from backend.tests.test_accounts import as_user, client  # noqa: F401  (shared fixture)


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
