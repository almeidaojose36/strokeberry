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

# What each plan includes. Both Free (3) and Pro (200) allowances are counted over a rolling 30 days, so a Free user's
# videos come back a month after they were made.
# "guest" is a visitor who hasn't signed in yet (a Firebase anonymous user): they can try the studio and preview
# drawings, but exporting needs a real account.
GUEST_PROJECT_LIMIT = 3
FREE_PRESET_LIMIT, PRO_PRESET_LIMIT = 1, 20
ACTIVE_RENDERS = {'free': 2, 'pro': 9}  # queued + rendering exports per person
PLANS = {
    'guest': {'name': 'Guest', 'exports': 0, 'period_days': None, 'max_resolution': '720p', 'max_duration': 60, 'watermark': True},
    'free': {'name': 'Free', 'exports': 3, 'period_days': 30, 'max_resolution': '720p', 'max_duration': 60, 'watermark': True},
    'pro': {'name': 'Pro', 'exports': 200, 'period_days': 30, 'max_resolution': '1080p', 'max_duration': 300, 'watermark': False},
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
    db.executescript('''CREATE TABLE IF NOT EXISTS presets (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
        settings TEXT NOT NULL, created TEXT);
        CREATE TABLE IF NOT EXISTS brand_kits (user_id TEXT PRIMARY KEY, name TEXT, ink_color TEXT, logo_corner TEXT DEFAULT 'bottom-right',
        has_logo INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1);''')
    if 'notices' not in {row[1] for row in db.execute('PRAGMA table_info(users)')}:
        db.execute("ALTER TABLE users ADD COLUMN notices TEXT NOT NULL DEFAULT '[]'")
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
    """Return (user_id, email, name, guest) for the caller, or raise 401."""
    mode = auth_mode()
    if mode == 'local':
        return LOCAL_USER, None, 'Local studio', False
    if mode == 'dev':
        # STROKEBERRY_DEV_USER lets a browser try the signed-in studio locally without Firebase.
        user = (request.headers.get('X-Dev-User') or os.environ.get('STROKEBERRY_DEV_USER', '')).strip()
        if not user:
            raise HTTPException(401, 'Please sign in to continue.')
        guest = bool(request.headers.get('X-Dev-Guest') or os.environ.get('STROKEBERRY_DEV_GUEST'))
        return user[:128], None if guest else f'{user[:64]}@example.test', user[:64], guest
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        raise HTTPException(401, 'Please sign in to continue.')
    claims = verify_firebase_token(header[7:])
    guest = (claims.get('firebase') or {}).get('sign_in_provider') == 'anonymous'
    return claims['sub'], claims.get('email'), claims.get('name'), guest


# ------------------------------------------------------------------------------------ users

def ensure_user(db, user_id, email=None, name=None, guest=False):
    row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if row is not None and row['plan'] == 'guest' and not guest:
        # The visitor signed in (their anonymous account was linked to Google or an email): same id, keeps their work.
        db.execute("UPDATE users SET plan='free' WHERE id=?", (user_id,))
        row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if row is None:
        # The local single-user studio keeps full features; real accounts start on Free, visitors as guests.
        plan = 'guest' if guest else os.environ.get('STROKEBERRY_LOCAL_PLAN', 'pro') if user_id == LOCAL_USER else 'free'
        # A new visitor's page fires several requests at once, so creating the row must tolerate a twin arriving first.
        db.execute('INSERT OR IGNORE INTO users (id, email, name, plan, created) VALUES (?,?,?,?,?)',
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
    resets = None
    if plan['period_days'] and used >= plan['exports'] > 0:
        # The allowance frees up when the video that pushes you over the limit turns a month old.
        row = db.execute(query.replace('count(*)', 'created') + ' ORDER BY created LIMIT 1 OFFSET ?', args + [used - plan['exports']]).fetchone()
        if row:
            resets = (datetime.fromisoformat(row[0]) + timedelta(days=plan['period_days'])).isoformat()
    return {'used': used, 'limit': plan['exports'], 'remaining': max(0, plan['exports'] - used),
            'period_days': plan['period_days'], 'resets': resets}


def short_date(iso):
    return datetime.fromisoformat(iso).strftime('%-d %b')


def account_summary(db, user):
    plan = plan_of(user)
    return {
        'user': {'id': user['id'], 'email': user['email'], 'name': user['name']},
        'plan': {'id': plan_id(user), **plan},
        'usage': usage(db, user),
        'billing': {'status': user.get('billing_status'), 'renews': user.get('plan_renews'),
                    'can_manage': bool(user.get('billing_subscription')), **billing_info()},
        'auth': auth_mode(),
    }


def billing_info():
    from . import billing
    return {'enabled': billing.configured(), 'monthly': billing.price('month'), 'yearly': billing.price('year'),
            'yearly_enabled': billing.configured('year'), 'yearly_saving': billing.yearly_saving(),
            'founder': billing.founder_offer()}


def check_duration(user, seconds):
    """Free videos can be up to a minute; longer ones (up to five minutes) are part of Pro."""
    limit = plan_of(user)['max_duration']
    if seconds > limit:
        raise HTTPException(403, 'Videos longer than 1 minute are part of Pro. Shorten this one or upgrade to make it up to 5 minutes.')


def check_export_allowed(db, user, settings):
    """Raise 402/403 with a friendly message when the plan doesn't allow this export."""
    plan = plan_of(user)
    if plan_id(user) == 'guest':
        raise HTTPException(401, 'Create a free account to export your video. It takes a few seconds.')
    check_duration(user, settings['duration'])
    if settings['resolution'] == '1080p' and plan['max_resolution'] != '1080p':
        raise HTTPException(403, 'Full HD 1080p is part of Strokeberry Pro. Choose 720p or upgrade.')
    if usage(db, user)['remaining'] <= 0:
        if plan_id(user) == 'free':
            when = usage(db, user)['resets']
            back = f' They come back on {short_date(when)}, or upgrade' if when else ' Upgrade'
            raise HTTPException(402, f"You've used your 3 free videos for this month.{back} to Pro to keep creating.")
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
