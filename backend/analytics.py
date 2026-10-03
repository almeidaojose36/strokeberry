"""Privacy-friendly funnel counts: no cookies, no third-party tracker, nothing stored in the visitor's browser.

A visitor is a hash of their IP address and browser with a random salt that changes every day and is then thrown away,
so the same person can be counted once per day but can't be recognised later or across days (the approach Plausible
uses). Page views are counted on the server as pages are served; the studio adds a few events of its own (the upgrade
dialog opening), and the server records the steps it already knows about (sign-up, project, export, checkout, payment).

`python -m backend.analytics [days]` prints the funnel.
"""
import hashlib
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

# Events the browser may send (everything else is recorded by the server itself).
CLIENT_EVENTS = {'upgrade_open', 'signin_open', 'pack_open'}
BOTS = re.compile(r'bot|crawl|spider|slurp|preview|monitor|headless|lighthouse|python|curl|wget|httpx|go-http|scan',
                  re.I)
PAGE = re.compile(r'^/(?:[a-z0-9-]+/)*(?:index\.html)?$', re.I)  # pages, not assets (assets have an extension)
SITE_HOSTS = ('strokeberry.com', 'www.strokeberry.com', 'localhost', '127.0.0.1')


def init(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS events (day TEXT, created TEXT, name TEXT, path TEXT, visitor TEXT,
                        user_id TEXT, source TEXT, detail TEXT);
                        CREATE INDEX IF NOT EXISTS events_day ON events (day, name);
                        CREATE TABLE IF NOT EXISTS analytics_salt (day TEXT PRIMARY KEY, salt TEXT);''')


def _today():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _salt(db, day):
    row = db.execute('SELECT salt FROM analytics_salt WHERE day=?', (day,)).fetchone()
    if row:
        return row[0]
    db.execute('DELETE FROM analytics_salt WHERE day<?', (day,))  # yesterday's salt is gone for good
    db.execute('INSERT OR IGNORE INTO analytics_salt (day, salt) VALUES (?,?)', (day, secrets.token_hex(16)))
    return db.execute('SELECT salt FROM analytics_salt WHERE day=?', (day,)).fetchone()[0]


def visitor(db, request):
    """Today's anonymous id for this browser, or None for bots."""
    agent = request.headers.get('user-agent', '')
    if not agent or BOTS.search(agent):
        return None
    ip = request.headers.get('cf-connecting-ip') or (request.client.host if request.client else '')
    day = _today()
    return hashlib.sha256(f'{_salt(db, day)}|{ip}|{agent}'.encode()).hexdigest()[:16]


def source(request):
    """Where the visit came from: a utm_source/ref tag, else the referring site (just its name), else None."""
    query = parse_qs(request.url.query)
    tag = (query.get('utm_source') or query.get('ref') or [''])[0].strip().lower()[:40]
    if tag:
        return tag
    host = urlparse(request.headers.get('referer', '')).hostname or ''
    host = host.removeprefix('www.').removeprefix('m.').removeprefix('l.')
    return host[:60] if host and host not in SITE_HOSTS else None


def record(db, name, request=None, user=None, detail=None, path=None):
    """Store one event. Never raises: analytics must not break the thing being measured."""
    try:
        who = visitor(db, request) if request is not None else None
        if request is not None and who is None and user is None:
            return  # a bot
        db.execute('INSERT INTO events (day, created, name, path, visitor, user_id, source, detail) VALUES (?,?,?,?,?,?,?,?)',
                   (_today(), datetime.now(timezone.utc).isoformat(timespec='seconds'), name,
                    path or (request.url.path if request is not None else None), who,
                    user['id'] if user else None, source(request) if request is not None else None,
                    str(detail)[:40] if detail is not None else None))
    except Exception:  # noqa: BLE001
        pass


def is_page_view(request, status):
    return (request.method == 'GET' and status == 200 and PAGE.match(request.url.path)
            and not request.url.path.startswith(('/api/', '/media/'))
            and 'text/html' in request.headers.get('accept', '')
            and request.headers.get('purpose') != 'prefetch' and request.headers.get('sec-purpose') is None)


# ------------------------------------------------------------------------------------ report

FUNNEL = [
    ('Visited the site', "name='pageview'", 'visitor'),
    ('Opened the studio', "name='pageview' AND path LIKE '/studio%'", 'visitor'),
    ('Uploaded their own image', "name='project' AND detail='upload'", 'user_id'),
    ('Created a free account', "name='signup'", 'user_id'),
    ('Exported a video', "name='export'", 'user_id'),
    ('Saw the upgrade offer', "name IN ('upgrade_open','pack_open')", 'user_id'),
    ('Reserved a founding place', "name='reserve'", 'user_id'),
    ('Started a checkout', "name='checkout'", 'user_id'),
    ('Paid (Pro or a pack)', "name='paid'", 'user_id'),
]


def report(db, days=30):
    since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime('%Y-%m-%d')
    out = [f'Strokeberry funnel, last {days} days (since {since})', '']
    first = None
    for label, where, key in FUNNEL:
        # visitors are counted once per day (their id changes daily); people with an account once overall
        count_expr = "count(DISTINCT day || visitor)" if key == 'visitor' else 'count(DISTINCT user_id)'
        n = db.execute(f'SELECT {count_expr} FROM events WHERE day>=? AND {where}', (since,)).fetchone()[0]
        first = first or n
        share = f'{n / first * 100:5.1f}%' if first else '    -'
        out.append(f'  {label:<28}{n:>7}  {share}')
    views = db.execute("SELECT count(*) FROM events WHERE day>=? AND name='pageview'", (since,)).fetchone()[0]
    exports = db.execute("SELECT detail, count(*) FROM events WHERE day>=? AND name='export' GROUP BY detail", (since,)).fetchall()
    out += ['', f'  Page views: {views}', '  Exports by plan: ' + (', '.join(f'{d or "?"} {n}' for d, n in exports) or 'none')]
    for title, sql in (
            ('Top pages', "SELECT path, count(DISTINCT day || visitor) n FROM events WHERE day>=? AND name='pageview' GROUP BY path ORDER BY n DESC LIMIT 10"),
            ('Where visitors came from', "SELECT source, count(DISTINCT day || visitor) n FROM events WHERE day>=? AND name='pageview' AND source IS NOT NULL GROUP BY source ORDER BY n DESC LIMIT 10")):
        rows = db.execute(sql, (since,)).fetchall()
        out += ['', f'  {title}:'] + ([f'    {n:>6}  {name}' for name, n in rows] or ['    (none yet)'])
    daily = db.execute("SELECT day, count(DISTINCT visitor) FROM events WHERE day>=? AND name='pageview' GROUP BY day ORDER BY day DESC LIMIT 14", (since,)).fetchall()
    out += ['', '  Visitors per day:'] + ([f'    {d}  {n}' for d, n in daily] or ['    (none yet)'])
    return '\n'.join(out)


if __name__ == '__main__':
    from .app import connect, init_db
    init_db()
    with connect() as connection:
        print(report(connection, int(sys.argv[1]) if len(sys.argv) > 1 else 30))
