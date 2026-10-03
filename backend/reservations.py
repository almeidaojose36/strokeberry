"""Founding-member reservations, for while payments aren't live yet (Lemon Squeezy still in test mode).

With STROKEBERRY_RESERVATIONS=1 the studio offers "Reserve my place" instead of a checkout: a signed-in member claims one of
the founding places (STROKEBERRY_FOUNDER_LIMIT, default 100) at the founding price, pays nothing, and gets GIFT
watermark-free videos straight away (added as pack videos, so they export like a pack: no watermark or end card, up to
5 minutes, 1080p). Checkouts are refused meanwhile, so nobody lands on a test-mode payment page.

When payments go live: switch STROKEBERRY_RESERVATIONS off, make sure the founder discount in Lemon Squeezy allows at
least as many redemptions as there are reservations, then run

    python -m backend.reservations            list the reservations
    python -m backend.reservations notify     email everyone who reserved (once each) that their price is ready to claim
"""
import os
import sys
from datetime import datetime, timezone

from fastapi import HTTPException

from . import analytics, mailer

GIFT = 3  # watermark-free videos for reserving


def enabled():
    return os.environ.get('STROKEBERRY_RESERVATIONS', '').strip().lower() in ('1', 'true', 'yes', 'on')


def init(db):
    db.execute('''CREATE TABLE IF NOT EXISTS reservations (user_id TEXT PRIMARY KEY, position INTEGER, email TEXT,
                  created TEXT, notified TEXT)''')


def limit():
    return int(os.environ.get('STROKEBERRY_FOUNDER_LIMIT', '100') or 100)


def offer(db):
    """The founding offer as the site shows it while reservations are open: {'price', 'limit', 'left'}, or None when full."""
    taken = db.execute('SELECT count(*) FROM reservations').fetchone()[0]
    left = max(0, limit() - taken)
    return {'price': os.environ.get('STROKEBERRY_FOUNDER_PRICE', '$7'), 'limit': limit(), 'left': left} if left else None


def mine(db, user):
    row = db.execute('SELECT position FROM reservations WHERE user_id=?', (user['id'],)).fetchone()
    return {'position': row[0]} if row else None


def reserve(db, user):
    """Claim a founding place for this member (once). Returns {'position', 'gift', 'new'}."""
    if not enabled():
        raise HTTPException(409, 'Founding places are claimed at checkout now. Open the upgrade options to go Pro.')
    if not user.get('email'):
        raise HTTPException(401, 'Sign in with Google or your email to reserve a place.')
    existing = mine(db, user)
    if existing:
        return dict(existing, gift=0, new=False)
    # One writer at a time, so two people can never get the same number or the 101st place.
    db.execute('BEGIN IMMEDIATE')
    taken = db.execute('SELECT count(*) FROM reservations').fetchone()[0]
    if taken >= limit():
        db.rollback()
        raise HTTPException(409, 'All founding places have been reserved. Payments open very soon.')
    position = taken + 1
    db.execute('INSERT INTO reservations (user_id, position, email, created) VALUES (?,?,?,?)',
               (user['id'], position, user['email'], datetime.now(timezone.utc).isoformat()))
    db.execute('UPDATE users SET pack_videos=pack_videos+? WHERE id=?', (GIFT, user['id']))
    analytics.record(db, 'reserve', user=user, detail=position)
    db.commit()
    mailer.reserved(user['email'], position, limit(), os.environ.get('STROKEBERRY_FOUNDER_PRICE', '$7'), GIFT, user.get('name'))
    return {'position': position, 'gift': GIFT, 'new': True}


def notify(db):
    """Email every member who reserved and hasn't been told yet that the founding price is ready to claim."""
    rows = db.execute('SELECT user_id, email FROM reservations WHERE notified IS NULL ORDER BY position').fetchall()
    sent = 0
    for user_id, email in rows:
        if mailer.founding_open(email, os.environ.get('STROKEBERRY_FOUNDER_PRICE', '$7')):
            db.execute('UPDATE reservations SET notified=? WHERE user_id=?', (datetime.now(timezone.utc).isoformat(), user_id))
            sent += 1
    db.commit()
    return sent


if __name__ == '__main__':
    from .app import connect, init_db, load_env_file
    load_env_file()
    init_db()
    with connect() as connection:
        if sys.argv[1:] == ['notify']:
            if enabled():
                sys.exit('Switch STROKEBERRY_RESERVATIONS off (payments live) before telling people to claim their price.')
            print(f'Emailed {notify(connection)} member(s).')
        else:
            rows = connection.execute('SELECT position, email, created, notified FROM reservations ORDER BY position').fetchall()
            print(f'{len(rows)} of {limit()} founding places reserved')
            for position, email, created, notified in rows:
                print(f'  #{position:<4}{email:<40}{created[:10]}  {"notified " + notified[:10] if notified else ""}')
