"""One-time video packs: bought through Lemon Squeezy, counted in videos, never expiring."""
import pytest

from backend import app as module, billing
from backend.tests.test_accounts import as_user, client, upload  # noqa: F401  (shared fixture)
from backend.tests.test_billing import post, webhook  # noqa: F401


def order(name='order_created', status='paid', pack='15', user_id='ana', order_id='ord_1'):
    return {'meta': {'event_name': name, 'custom_data': {'user_id': user_id, 'pack': pack}},
            'data': {'type': 'orders', 'id': order_id, 'attributes': {'status': status}}}


def me(client, user='ana'):
    return client.get('/api/me', headers=as_user(user)).json()


def test_a_paid_pack_order_is_credited_once_and_taken_back_on_refund(client, webhook):
    me(client)
    assert post(client, order()).status_code == 200
    assert post(client, order()).status_code == 200            # Lemon Squeezy may deliver the same webhook twice
    assert me(client)['packs'] == 15
    post(client, order(status='pending', order_id='ord_2'))     # unpaid orders add nothing
    post(client, order(pack='7', order_id='ord_3'))             # nor do made-up pack sizes
    assert me(client)['packs'] == 15
    post(client, order(name='order_refunded'))
    post(client, order(name='order_refunded'))
    assert me(client)['packs'] == 0


def test_pack_videos_export_like_pro_and_are_refunded_when_a_render_fails(client):
    project = upload(client, 'ana')
    url = f"/api/projects/{project['id']}/jobs"
    with module.connect() as db:
        db.execute("UPDATE users SET pack_videos=2 WHERE id='ana'")
    assert client.post(url, headers=as_user('ana'), json={'resolution': '4k'}).status_code == 403   # 4K stays Pro
    made = client.post(url, headers=as_user('ana'), json={'duration': 240, 'resolution': '1080p'})
    assert made.status_code == 202, made.text                                                   # up to 5 minutes
    settings = client.submitted[-1][3]
    assert settings['watermark'] is False and settings['end_card'] is False
    account = me(client)
    assert account['packs'] == 1 and account['usage']['remaining'] == 3    # the free allowance is untouched
    with module.connect() as db:
        module.accounts.refund_failed(db, [made.json()['id']])
        module.accounts.refund_failed(db, [made.json()['id']])            # never twice
    assert me(client)['packs'] == 2


def test_deleting_an_export_does_not_give_the_month_allowance_back(client):
    project = upload(client, 'ana')
    job = client.post(f"/api/projects/{project['id']}/jobs", headers=as_user('ana'), json={}).json()
    with module.connect() as db:
        db.execute("UPDATE jobs SET status='completed'")
    assert client.delete(f"/api/jobs/{job['id']}", headers=as_user('ana')).status_code == 204
    assert me(client)['usage']['remaining'] == 2
    assert client.get(f"/api/jobs/{job['id']}", headers=as_user('ana')).status_code == 404
    assert client.get('/api/jobs', headers=as_user('ana')).json() == []


def test_packs_are_listed_only_when_their_products_exist(monkeypatch):
    assert billing.packs() == []
    for key, value in {'LEMONSQUEEZY_API_KEY': 'k', 'LEMONSQUEEZY_STORE_ID': '1', 'LEMONSQUEEZY_PACK_5_VARIANT_ID': '11',
                       'LEMONSQUEEZY_PACK_40_VARIANT_ID': '13'}.items():
        monkeypatch.setenv(key, value)
    offered = billing.packs()
    assert [p['videos'] for p in offered] == [5, 40]
    assert offered[1]['label'] == 'Best value' and offered[1]['per_video'] == '$0.62'
    assert offered[0]['per_video'] == '$1.00'


def test_guests_cannot_buy_packs(client):
    response = client.post('/api/billing/pack', headers={**as_user('gus'), 'X-Dev-Guest': '1'}, json={'pack': '5'})
    assert response.status_code == 401
