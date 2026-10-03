"""Founding-member reservations while payments aren't live."""
import pytest

from backend import mailer
from backend.tests.test_accounts import as_user, client  # noqa: F401  (shared fixture)


@pytest.fixture
def reserving(monkeypatch):
    monkeypatch.setenv('STROKEBERRY_RESERVATIONS', '1')
    monkeypatch.setenv('STROKEBERRY_FOUNDER_LIMIT', '2')
    sent = []
    monkeypatch.setattr(mailer, 'reserved', lambda *args, **kwargs: sent.append(args) or True)
    return sent


def me(client, user):
    return client.get('/api/me', headers=as_user(user)).json()


def test_reserving_a_place_gives_a_number_and_watermark_free_videos_once(client, reserving):
    account = me(client, 'ana')
    assert account['billing']['reserve'] and account['billing']['founder']['left'] == 2 and account['billing']['packs'] == []
    first = client.post('/api/reserve', headers=as_user('ana')).json()
    assert first == {'position': 1, 'gift': 3, 'new': True}
    again = client.post('/api/reserve', headers=as_user('ana')).json()
    assert again['position'] == 1 and again['gift'] == 0           # reserving twice changes nothing
    account = me(client, 'ana')
    assert account['packs'] == 3 and account['billing']['reservation'] == {'position': 1}
    assert account['billing']['founder']['left'] == 1
    assert len(reserving) == 1 and reserving[0][1] == 1           # one confirmation email, for place #1


def test_places_run_out_and_checkouts_are_refused_meanwhile(client, reserving):
    for user in ('ana', 'ben'):
        assert client.post('/api/reserve', headers=as_user(user)).status_code == 200
    full = client.post('/api/reserve', headers=as_user('cleo'))
    assert full.status_code == 409 and 'All founding places' in full.json()['detail']
    assert me(client, 'cleo')['billing']['founder'] is None
    assert client.post('/api/billing/checkout', headers=as_user('cleo'), json={}).status_code == 409
    assert client.post('/api/billing/pack', headers=as_user('cleo'), json={'pack': '5'}).status_code == 409
    assert client.get('/api/offer').json()['founder'] is None


def test_guests_sign_up_first_and_reservations_are_off_by_default(client, monkeypatch):
    monkeypatch.setenv('STROKEBERRY_RESERVATIONS', '1')
    guest = client.post('/api/reserve', headers={**as_user('visitor'), 'X-Dev-Guest': '1'})
    assert guest.status_code == 401
    monkeypatch.delenv('STROKEBERRY_RESERVATIONS')
    assert client.post('/api/reserve', headers=as_user('ana')).status_code == 409
    assert 'reserve' not in me(client, 'ana')['billing']
