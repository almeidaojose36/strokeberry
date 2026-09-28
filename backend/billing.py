"""Lemon Squeezy billing: checkout links, the subscription webhook, and the customer portal.

Configure with environment variables (keep the secret ones in .env.local, never in git):
  LEMONSQUEEZY_API_KEY          API key (Settings → API). Test-mode keys work with test-mode stores.
  LEMONSQUEEZY_STORE_ID         numeric store id
  LEMONSQUEEZY_PRO_VARIANT_ID   numeric variant id of the "Pro" monthly product
  LEMONSQUEEZY_WEBHOOK_SECRET   the signing secret you set on the webhook (Settings → Webhooks)
  STROKEBERRY_APP_URL           public site address, e.g. https://strokeberry.com (checkout returns here)

Lemon Squeezy is the merchant of record: it charges customers, handles VAT/sales tax and pays out.
Our database only mirrors the subscription state it sends us through the webhook.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

API = 'https://api.lemonsqueezy.com/v1'
# Subscription statuses that still give Pro. "past_due" keeps access while Lemon Squeezy retries the card.
ACTIVE = {'on_trial', 'active', 'past_due'}


def configured():
    return all(os.environ.get(k) for k in ('LEMONSQUEEZY_API_KEY', 'LEMONSQUEEZY_STORE_ID', 'LEMONSQUEEZY_PRO_VARIANT_ID'))


def _headers():
    return {'Accept': 'application/vnd.api+json', 'Content-Type': 'application/vnd.api+json',
            'Authorization': f"Bearer {os.environ['LEMONSQUEEZY_API_KEY']}"}


def create_checkout(user):
    """Return a hosted checkout URL for the Pro plan, tagged with our user id."""
    if not configured():
        raise HTTPException(503, 'Payments are not set up yet. Please check back soon.')
    app_url = os.environ.get('STROKEBERRY_APP_URL', 'http://127.0.0.1:8001').rstrip('/')
    checkout_data = {'custom': {'user_id': user['id']}}
    if user.get('email'):
        checkout_data['email'] = user['email']
    body = {'data': {
        'type': 'checkouts',
        'attributes': {
            'checkout_data': checkout_data,
            'product_options': {'redirect_url': f'{app_url}/studio/?upgraded=1'},
            'checkout_options': {'embed': False},
        },
        'relationships': {
            'store': {'data': {'type': 'stores', 'id': str(os.environ['LEMONSQUEEZY_STORE_ID'])}},
            'variant': {'data': {'type': 'variants', 'id': str(os.environ['LEMONSQUEEZY_PRO_VARIANT_ID'])}},
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


def apply_webhook(db, payload):
    """Mirror a subscription event onto the user. Returns the user id it applied to, or None."""
    event = payload.get('meta', {}).get('event_name', '')
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
