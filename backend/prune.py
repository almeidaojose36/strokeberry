"""Remove abandoned guest data.

    .venv/bin/python -m backend.prune          # run daily, e.g. from cron

Firebase deletes anonymous (guest) accounts 30 days after they are created (auto clean-up is switched on), so their projects
and videos would otherwise sit on the server forever. This deletes guests older than 30 days together with their files.
People who signed in are never touched: their account stops being a guest the moment they do.
"""
import shutil
import sys
from datetime import datetime, timedelta, timezone

GUEST_DAYS = 30


def prune_guests(db, data_dir, now=None, days=GUEST_DAYS):
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=days)).isoformat()
    guests = [row['id'] for row in db.execute("SELECT id FROM users WHERE plan='guest' AND created < ?", (cutoff,))]
    for user_id in guests:
        for row in db.execute('SELECT id FROM projects WHERE user_id=?', (user_id,)).fetchall():
            shutil.rmtree(data_dir / row['id'], ignore_errors=True)
        db.execute('DELETE FROM jobs WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM projects WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM presets WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM brand_kits WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM users WHERE id=?', (user_id,))
    return len(guests)


if __name__ == '__main__':
    from . import app as module
    module.init_db()
    with module.connect() as db:
        print(f'Removed {prune_guests(db, module.DATA)} abandoned guest account(s).', file=sys.stderr)
