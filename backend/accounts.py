"""Users, sign-in, plans and usage limits.

Sign-in modes (chosen from the environment at request time):
- FIREBASE_PROJECT_ID set: every API call needs `Authorization: Bearer <Firebase ID token>`.
- STROKEBERRY_AUTH=dev: tests and local development identify the user with an `X-Dev-User` header
  (or STROKEBERRY_DEV_USER when the header is absent).
- neither: the app runs as a single local user ("local"), the way the studio has always worked on one computer.

Media and video files are loaded by <img>/<video> tags, which cannot send headers, so their URLs carry a
short-lived HMAC signature instead (see sign_url / verify_signature).
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import jwt
from fastapi import HTTPException, Request

FIREBASE_JWKS = 'https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com'
LOCAL_USER = 'local'

# What each plan includes. Free exports count for the lifetime of the account; Pro exports reset every 30 days.
PLANS = {
    'free': {'name': 'Free', 'exports': 3, 'period_days': None, 'max_resolution': '720p', 'watermark': True},
    'pro': {'name': 'Pro', 'exports': 200, 'period_days': 30, 'max_resolution': '1080p', 'watermark': False},
}

_jwks_lock = threading.Lock()
_jwks_cache = {'keys': None, 'fetched': 0.0}


def auth_mode():
    if os.environ.get('FIREBASE_PROJECT_ID'):
        return 'firebase'
    if os.environ.get('STROKEBERRY_AUTH') == 'dev':
        return 'dev'
    return 'local'


def init_accounts(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, email TEXT, name TEXT, plan TEXT NOT NULL DEFAULT 'free', created TEXT,
        billing_customer TEXT, billing_subscription TEXT, billing_status TEXT, plan_renews TEXT, billing_portal TEXT);''')
    for table in ('projects', 'jobs'):
        columns = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
        if 'user_id' not in columns:
            # Everything created before accounts existed belongs to the local single-user studio.
            db.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT NOT NULL DEFAULT '{LOCAL_USER}'")


# ----------------------------------------------------------------------------------- tokens

def _firebase_keys(force=False):
    with _jwks_lock:
        fresh = time.time() - _jwks_cache['fetched'] < 3600
        if _jwks_cache['keys'] is None or force or not fresh:
            with urllib.request.urlopen(FIREBASE_JWKS, timeout=10) as response:
                _jwks_cache['keys'] = {k['kid']: k for k in json.load(response)['keys']}
                _jwks_cache['fetched'] = time.time()
        return _jwks_cache['keys']


def verify_firebase_token(token):
    """Check a Firebase ID token's signature, audience, issuer and expiry. Returns its claims."""
    project = os.environ['FIREBASE_PROJECT_ID']
    try:
        kid = jwt.get_unverified_header(token).get('kid')
        keys = _firebase_keys()
        if kid not in keys:
            keys = _firebase_keys(force=True)
        key = jwt.PyJWK(keys[kid]).key
        claims = jwt.decode(token, key, algorithms=['RS256'], audience=project,
                            issuer=f'https://securetoken.google.com/{project}', leeway=30)
    except (jwt.PyJWTError, KeyError, ValueError, OSError):
        raise HTTPException(401, 'Please sign in again.')
    if not claims.get('sub'):
        raise HTTPException(401, 'Please sign in again.')
    return claims


def identify(request: Request):
    """Return (user_id, email, name) for the caller, or raise 401."""
    mode = auth_mode()
    if mode == 'local':
        return LOCAL_USER, None, 'Local studio'
    if mode == 'dev':
        # STROKEBERRY_DEV_USER lets a browser try the signed-in studio locally without Firebase.
        user = (request.headers.get('X-Dev-User') or os.environ.get('STROKEBERRY_DEV_USER', '')).strip()
        if not user:
            raise HTTPException(401, 'Please sign in to continue.')
        return user[:128], f'{user[:64]}@example.test', user[:64]
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        raise HTTPException(401, 'Please sign in to continue.')
    claims = verify_firebase_token(header[7:])
    return claims['sub'], claims.get('email'), claims.get('name')


# ------------------------------------------------------------------------------------ users

def ensure_user(db, user_id, email=None, name=None):
    row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if row is None:
        # The local single-user studio keeps full features; real accounts start on Free.
        plan = os.environ.get('STROKEBERRY_LOCAL_PLAN', 'pro') if user_id == LOCAL_USER else 'free'
        db.execute('INSERT INTO users (id, email, name, plan, created) VALUES (?,?,?,?,?)',
                   (user_id, email, name, plan if plan in PLANS else 'free', now()))
        row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    elif (email and email != row['email']) or (name and name != row['name']):
        db.execute('UPDATE users SET email=COALESCE(?, email), name=COALESCE(?, name) WHERE id=?', (email, name, user_id))
        row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    return dict(row)


def now():
    return datetime.now(timezone.utc).isoformat()


def plan_id(user):
    """The plan in force now. A cancelled Pro subscription lapses by itself once its paid period ends,
    even if the expiry webhook never arrives."""
    if user['plan'] == 'pro' and user.get('billing_status') in ('cancelled', 'expired') and user.get('plan_renews'):
        try:
            ends = datetime.fromisoformat(user['plan_renews'].replace('Z', '+00:00'))
            if ends <= datetime.now(timezone.utc):
                return 'free'
        except ValueError:
            pass
    return user['plan'] if user['plan'] in PLANS else 'free'


def plan_of(user):
    return PLANS[plan_id(user)]


def usage(db, user):
    plan = plan_of(user)
    query = "SELECT count(*) FROM jobs WHERE user_id=? AND status != 'failed'"
    args = [user['id']]
    if plan['period_days']:
        query += ' AND created >= ?'
        args.append((datetime.now(timezone.utc) - timedelta(days=plan['period_days'])).isoformat())
    used = db.execute(query, args).fetchone()[0]
    return {'used': used, 'limit': plan['exports'], 'remaining': max(0, plan['exports'] - used),
            'period_days': plan['period_days']}


def account_summary(db, user):
    plan = plan_of(user)
    return {
        'user': {'id': user['id'], 'email': user['email'], 'name': user['name']},
        'plan': {'id': plan_id(user), **plan},
        'usage': usage(db, user),
        'billing': {'status': user.get('billing_status'), 'renews': user.get('plan_renews'),
                    'can_manage': bool(user.get('billing_subscription')),
                    'enabled': billing_enabled(), 'price': os.environ.get('STROKEBERRY_PRO_PRICE', '$9 / month')},
        'auth': auth_mode(),
    }


def billing_enabled():
    from .billing import configured
    return configured()


def check_export_allowed(db, user, settings):
    """Raise 402/403 with a friendly message when the plan doesn't allow this export."""
    plan = plan_of(user)
    if settings['resolution'] == '1080p' and plan['max_resolution'] != '1080p':
        raise HTTPException(403, 'Full HD 1080p is part of Strokeberry Pro. Choose 720p or upgrade.')
    if usage(db, user)['remaining'] <= 0:
        if plan_id(user) == 'free':
            raise HTTPException(402, "You've used your free videos. Upgrade to Pro to keep creating.")
        raise HTTPException(429, "You've reached this month's export limit. It resets soon — thanks for creating so much!")
    return plan


# ------------------------------------------------------------------------------ signed URLs

def _secret(data_dir: Path):
    value = os.environ.get('STROKEBERRY_SECRET')
    if value:
        return value.encode()
    path = data_dir / 'secret.key'
    if not path.exists():
        path.write_text(secrets.token_hex(32))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_text().strip().encode()


def sign_url(data_dir, path, ttl=24 * 3600):
    """Append an expiring signature so <img>/<video> tags can load a private file."""
    expires = int(time.time()) + ttl
    signature = hmac.new(_secret(data_dir), f'{path}:{expires}'.encode(), hashlib.sha256).hexdigest()[:32]
    return f'{path}?{urlencode({"e": expires, "s": signature})}'


def verify_signature(data_dir, path, expires: Optional[str], signature: Optional[str]):
    if auth_mode() == 'local' and not signature:
        return  # single-user local studio: files are only reachable on this machine
    try:
        expires_at = int(expires or 0)
    except ValueError:
        expires_at = 0
    expected = hmac.new(_secret(data_dir), f'{path}:{expires_at}'.encode(), hashlib.sha256).hexdigest()[:32]
    if expires_at < time.time() or not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(403, 'This link has expired. Reload the page to get a fresh one.')
