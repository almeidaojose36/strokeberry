"""Lemon Squeezy billing: checkout links, the subscription webhook, and the customer portal.

Configure with environment variables (keep the secret ones in .env.local, never in git):
  LEMONSQUEEZY_API_KEY          API key (Settings → API). Test-mode keys work with test-mode stores.
  LEMONSQUEEZY_STORE_ID         numeric store id
  LEMONSQUEEZY_PRO_VARIANT_ID   numeric variant id of the "Pro" monthly product
  LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID  (optional) variant id of the yearly price; the yearly option shows only when set
  STROKEBERRY_FOUNDER_CODE      (optional) turns on the "Founding member" offer. In Lemon Squeezy create a discount with this
                                code: 30% off, duration "forever", limited to 100 redemptions, applying to the monthly variant
                                only. It is applied automatically to monthly checkouts and shown on the site.
  STROKEBERRY_FOUNDER_PRICE / STROKEBERRY_FOUNDER_LIMIT   display values, default "$7" and 100
  STROKEBERRY_PRICE_MONTH / STROKEBERRY_PRICE_YEAR  the prices shown to visitors, e.g. "$10" and "$84" (display only;
                                the amount charged is whatever the Lemon Squeezy variant says)
  LEMONSQUEEZY_PACK_5_VARIANT_ID / _15_ / _40_   (optional) one-time "video pack" products of 5, 15 and 40 videos; each
                                pack shows only when its variant id is set. Display prices below (the charge is the variant's).
  STROKEBERRY_PACK_PRICES       display prices for the 5/15/40 packs, default "$5,$12,$25"
  LEMONSQUEEZY_WEBHOOK_SECRET   the signing secret you set on the webhook (Settings → Webhooks)
  STROKEBERRY_APP_URL           public site address, e.g. https://strokeberry.com (checkout returns here)

Lemon Squeezy is the merchant of record: it charges customers, handles VAT/sales tax and pays out.
Our database only mirrors the subscription state it sends us through the webhook.
"""
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

API = 'https://api.lemonsqueezy.com/v1'
# Subscription statuses that still give Pro. "past_due" keeps access while Lemon Squeezy retries the card.
ACTIVE = {'on_trial', 'active', 'past_due'}


# One-time video packs, counted in videos (never per second) and never expiring. Bigger packs cost less per video, but every
# pack costs more per video than Pro, so people who create regularly are better off subscribing.
PACK_SIZES = (5, 15, 40)
PACK_LABELS = {15: 'Most popular', 40: 'Best value'}


def packs():
    """The video packs on sale: [{'id', 'videos', 'price', 'per_video', 'label'}]. Empty when payments aren't set up."""
    prices = (os.environ.get('STROKEBERRY_PACK_PRICES') or '$5,$12,$25').split(',')
    offered = []
    for size, shown in zip(PACK_SIZES, prices):
        if not (os.environ.get(f'LEMONSQUEEZY_PACK_{size}_VARIANT_ID') and os.environ.get('LEMONSQUEEZY_API_KEY')
                and os.environ.get('LEMONSQUEEZY_STORE_ID')):
            continue
        shown = shown.strip()
        try:
            per_video = f'${float(shown.lstrip("$")) / size:.2f}'
        except ValueError:
            per_video = None
        offered.append({'id': str(size), 'videos': size, 'price': shown, 'per_video': per_video, 'label': PACK_LABELS.get(size)})
    return offered


def configured(interval='month'):
    variant = 'LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID' if interval == 'year' else 'LEMONSQUEEZY_PRO_VARIANT_ID'
    return all(os.environ.get(k) for k in ('LEMONSQUEEZY_API_KEY', 'LEMONSQUEEZY_STORE_ID', variant))


def price(interval='month'):
    return os.environ.get('STROKEBERRY_PRICE_YEAR', '$84') if interval == 'year' else os.environ.get('STROKEBERRY_PRICE_MONTH', '$10')


_offer_cache = {'at': 0.0, 'value': None}


def founder_offer():
    """The Founding member offer (or None when it isn't switched on or has sold out).

    {'price', 'limit', 'left'}; `left` is None when Lemon Squeezy can't be asked, in which case the offer is still shown
    without a counter. Cached for five minutes."""
    code = os.environ.get('STROKEBERRY_FOUNDER_CODE', '').strip()
    if not code or not configured():
        return None
    if time.time() - _offer_cache['at'] < 300 and _offer_cache.get('code') == code:
        return _offer_cache['value']
    limit = int(os.environ.get('STROKEBERRY_FOUNDER_LIMIT', '100') or 100)
    left = None
    try:
        found = httpx.get(f'{API}/discounts', headers=_headers(), timeout=10,
                          params={'filter[store_id]': os.environ['LEMONSQUEEZY_STORE_ID'], 'page[size]': 100})
        found.raise_for_status()
        discount = next((d for d in found.json()['data'] if d['attributes'].get('code', '').lower() == code.lower()), None)
        if discount:
            limit = int(discount['attributes'].get('max_redemptions') or limit)
            used = httpx.get(f'{API}/discount-redemptions', headers=_headers(), timeout=10,
                             params={'filter[discount_id]': discount['id'], 'page[size]': 1})
            used.raise_for_status()
            left = max(0, limit - int(used.json()['meta']['page']['total']))
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        left = None
    offer = None if left == 0 else {'price': os.environ.get('STROKEBERRY_FOUNDER_PRICE', '$7'), 'limit': limit, 'left': left}
    _offer_cache.update(at=time.time(), value=offer, code=code)
    return offer


def yearly_saving():
    """How much cheaper the yearly plan is than twelve monthly payments, as a whole percentage."""
    try:
        monthly = float(price('month').lstrip('$'))
        yearly = float(price('year').lstrip('$'))
        return max(0, round((1 - yearly / (monthly * 12)) * 100))
    except ValueError:
        return 0


def _headers():
    return {'Accept': 'application/vnd.api+json', 'Content-Type': 'application/vnd.api+json',
            'Authorization': f"Bearer {os.environ['LEMONSQUEEZY_API_KEY']}"}


def create_checkout(user, interval='month'):
    """Return a hosted checkout URL for the Pro plan (monthly or yearly), tagged with our user id."""
    if not configured(interval):
        raise HTTPException(503, 'Payments are not set up yet. Please check back soon.')
    checkout_data = {'custom': {'user_id': user['id']}}
    if interval == 'month' and founder_offer():  # the yearly plan is already discounted, so the code isn't stacked on it
        checkout_data['discount_code'] = os.environ['STROKEBERRY_FOUNDER_CODE'].strip()
    variant = os.environ['LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID' if interval == 'year' else 'LEMONSQUEEZY_PRO_VARIANT_ID']
    return _checkout(user, checkout_data, variant, 'upgraded=1')


def create_pack_checkout(user, pack):
    """Return a hosted checkout URL for a one-time video pack."""
    if not any(p['id'] == str(pack) for p in packs()):
        raise HTTPException(404, 'That video pack is not available.')
    variant = os.environ[f'LEMONSQUEEZY_PACK_{pack}_VARIANT_ID']
    return _checkout(user, {'custom': {'user_id': user['id'], 'pack': str(pack)}}, variant, f'pack={pack}')


def _checkout(user, checkout_data, variant, returned):
    app_url = os.environ.get('STROKEBERRY_APP_URL', 'http://127.0.0.1:8001').rstrip('/')
    if user.get('email'):
        checkout_data['email'] = user['email']
    body = {'data': {
        'type': 'checkouts',
        'attributes': {
            'checkout_data': checkout_data,
            'product_options': {'redirect_url': f'{app_url}/studio/?{returned}'},
            'checkout_options': {'embed': False},
        },
        'relationships': {
            'store': {'data': {'type': 'stores', 'id': str(os.environ['LEMONSQUEEZY_STORE_ID'])}},
            'variant': {'data': {'type': 'variants', 'id': str(variant)}},
        },
    }}
    try:
        response = httpx.post(f'{API}/checkouts', headers=_headers(), json=body, timeout=20)
        response.raise_for_status()
        return response.json()['data']['attributes']['url']
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(502, "We couldn't open the checkout just now. Please try again in a minute.")


def portal_url(user):
    """A fresh customer-portal link (Lemon Squeezy's signed links expire after 24 hours)."""
    subscription = user.get('billing_subscription')
    if not subscription:
        raise HTTPException(404, "You don't have a subscription to manage yet.")
    if configured():
        try:
            response = httpx.get(f'{API}/subscriptions/{subscription}', headers=_headers(), timeout=20)
            response.raise_for_status()
            return response.json()['data']['attributes']['urls']['customer_portal']
        except (httpx.HTTPError, KeyError, ValueError):
            pass
    if user.get('billing_portal'):
        return user['billing_portal']
    raise HTTPException(502, "We couldn't open billing just now. Please try again in a minute.")


def verify_webhook(raw: bytes, signature: str):
    secret = os.environ.get('LEMONSQUEEZY_WEBHOOK_SECRET')
    if not secret:
        raise HTTPException(503, 'Webhook secret is not configured.')
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(401, 'Invalid signature.')


def _is_future(value):
    if not value:
        return False
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')) > datetime.now(timezone.utc)
    except ValueError:
        return False


def apply_pack_order(db, payload):
    """Credit (order_created, paid) or take back (order_refunded) a video pack. Each order counts once, however many
    times Lemon Squeezy delivers the webhook. Returns the user id, or None when the order isn't a pack."""
    event = payload.get('meta', {}).get('event_name', '')
    custom = payload.get('meta', {}).get('custom_data') or {}
    data = payload.get('data', {})
    order_id, user_id, pack = str(data.get('id') or ''), custom.get('user_id'), str(custom.get('pack') or '')
    if not (order_id and user_id and pack.isdigit() and int(pack) in PACK_SIZES):
        return None
    videos = int(pack)
    if event == 'order_created' and data.get('attributes', {}).get('status') == 'paid':
        if not db.execute('SELECT 1 FROM users WHERE id=?', (user_id,)).fetchone():
            return None
        added = db.execute('INSERT OR IGNORE INTO pack_orders (order_id, user_id, pack, videos, created) VALUES (?,?,?,?,?)',
                           (order_id, user_id, pack, videos, datetime.now(timezone.utc).isoformat())).rowcount
        if added:
            db.execute('UPDATE users SET pack_videos=pack_videos+? WHERE id=?', (videos, user_id))
        return user_id
    if event == 'order_refunded':
        taken = db.execute('UPDATE pack_orders SET refunded=1 WHERE order_id=? AND refunded=0', (order_id,)).rowcount
        if taken:
            db.execute('UPDATE users SET pack_videos=MAX(0, pack_videos-?) WHERE id=?', (videos, user_id))
        return user_id
    return None


def apply_webhook(db, payload):
    """Mirror a subscription event onto the user, or credit a video pack. Returns the user id it applied to, or None."""
    event = payload.get('meta', {}).get('event_name', '')
    if event.startswith('order_'):
        return apply_pack_order(db, payload)
    if not event.startswith('subscription_') or event.startswith('subscription_payment'):
        return None  # orders, refunds and payment receipts don't change the plan here
    data = payload.get('data', {})
    attributes = data.get('attributes', {})
    subscription_id = str(data.get('id') or '')
    user_id = (payload.get('meta', {}).get('custom_data') or {}).get('user_id')
    if not user_id and subscription_id:
        row = db.execute('SELECT id FROM users WHERE billing_subscription=?', (subscription_id,)).fetchone()
        user_id = row['id'] if row else None
    if not user_id:
        return None
    status = attributes.get('status', '')
    ends_at = attributes.get('ends_at')
    # A cancelled subscription keeps Pro until the end of the period that was paid for.
    pro = status in ACTIVE or (status == 'cancelled' and _is_future(ends_at))
    exists = db.execute('SELECT 1 FROM users WHERE id=?', (user_id,)).fetchone()
    if not exists:
        db.execute("INSERT INTO users (id, email, plan, created) VALUES (?,?,'free',?)",
                   (user_id, attributes.get('user_email'), datetime.now(timezone.utc).isoformat()))
    db.execute('''UPDATE users SET plan=?, billing_customer=?, billing_subscription=?, billing_status=?,
                  plan_renews=?, billing_portal=? WHERE id=?''',
               ('pro' if pro else 'free', str(attributes.get('customer_id') or ''), subscription_id, status,
                ends_at if status == 'cancelled' else attributes.get('renews_at'),
                (attributes.get('urls') or {}).get('customer_portal'), user_id))
    return user_id


def parse(raw: bytes):
    try:
        return json.loads(raw)
    except ValueError:
        raise HTTPException(400, 'Invalid JSON.')
