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
# Referral spam: sites (or their bots) that fake visits so their name shows up in analytics, e.g. increasebacklinks.site.
SPAM_WORDS = ('backlink', 'linkbuilding', 'link-building', 'dofollow', 'linkmanagement', 'seo', 'traffic',
              'buttons-for', 'free-share', 'social-buttons', 'best-price', 'linkgenerator', 'linkanalyz', 'linkanalys',
              'competitorlinks')


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


def is_spam(source_name):
    return bool(source_name) and any(word in source_name for word in SPAM_WORDS)


def record(db, name, request=None, user=None, detail=None, path=None):
    """Store one event. Never raises: analytics must not break the thing being measured."""
    try:
        who = visitor(db, request) if request is not None else None
        if request is not None and who is None and user is None:
            return  # a bot
        if name == 'pageview' and is_spam(source(request)):
            return  # referral spam, not a person
        db.execute('INSERT INTO events (day, created, name, path, visitor, user_id, source, detail) VALUES (?,?,?,?,?,?,?,?)',
                   (_today(), datetime.now(timezone.utc).isoformat(timespec='seconds'), name,
                    path or (request.url.path if request is not None else None), who,
                    user['id'] if user else None, source(request) if request is not None else None,
                    str(detail)[:40] if detail is not None else None))
    except Exception:  # noqa: BLE001
        pass


def is_page_view(request, status):
    return (request.method == 'GET' and status == 200 and PAGE.match(request.url.path)
            and not request.url.path.startswith(('/api/', '/media/', '/admin'))
            and 'text/html' in request.headers.get('accept', '')
            and request.headers.get('purpose') != 'prefetch' and request.headers.get('sec-purpose') is None)


# ------------------------------------------------------------------------------------ report

# Page views, without referral spam recorded before the filter existed.
VIEWS = "name='pageview' AND (source IS NULL OR NOT (" + ' OR '.join(f"source LIKE '%{w}%'" for w in SPAM_WORDS) + '))'
FUNNEL = [
    ('Visited the site', VIEWS, 'visitor'),
    ('Opened the studio', VIEWS + " AND path LIKE '/studio%'", 'visitor'),
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
    views = db.execute(f"SELECT count(*) FROM events WHERE day>=? AND {VIEWS}", (since,)).fetchone()[0]
    exports = db.execute("SELECT detail, count(*) FROM events WHERE day>=? AND name='export' GROUP BY detail", (since,)).fetchall()
    out += ['', f'  Page views: {views}', '  Exports by plan: ' + (', '.join(f'{d or "?"} {n}' for d, n in exports) or 'none')]
    for title, sql in (
            ('Top pages', f"SELECT path, count(DISTINCT day || visitor) n FROM events WHERE day>=? AND {VIEWS} GROUP BY path ORDER BY n DESC LIMIT 10"),
            ('Where visitors came from', f"SELECT source, count(DISTINCT day || visitor) n FROM events WHERE day>=? AND {VIEWS} AND source IS NOT NULL GROUP BY source ORDER BY n DESC LIMIT 10")):
        rows = db.execute(sql, (since,)).fetchall()
        out += ['', f'  {title}:'] + ([f'    {n:>6}  {name}' for name, n in rows] or ['    (none yet)'])
    daily = db.execute(f"SELECT day, count(DISTINCT visitor) FROM events WHERE day>=? AND {VIEWS} GROUP BY day ORDER BY day DESC LIMIT 14", (since,)).fetchall()
    out += ['', '  Visitors per day:'] + ([f'    {d}  {n}' for d, n in daily] or ['    (none yet)'])
    return '\n'.join(out)


def stats(db, days=7):
    """Everything the private dashboard shows, as plain data. days=1 is today (UTC); otherwise the last N days."""
    days = max(1, min(int(days), 90))
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days - 1)).strftime('%Y-%m-%d')
    before = (now - timedelta(days=2 * days - 1)).strftime('%Y-%m-%d')   # the same length of time just before, for comparison

    def count(where, key, start, end=None):
        expr = 'count(DISTINCT day || visitor)' if key == 'visitor' else 'count(DISTINCT user_id)'
        sql = f'SELECT {expr} FROM events WHERE day>=? AND {where}' + (' AND day<?' if end else '')
        return db.execute(sql, (start, end) if end else (start,)).fetchone()[0]

    funnel = [{'label': label, 'count': count(where, key, since), 'previous': count(where, key, before, since)}
              for label, where, key in FUNNEL]
    views = lambda start, end=None: db.execute(f"SELECT count(*) FROM events WHERE day>=? AND {VIEWS}" + (' AND day<?' if end else ''),
                                               (start, end) if end else (start,)).fetchone()[0]
    daily = {day: [visitors, page_views] for day, visitors, page_views in db.execute(
        f"SELECT day, count(DISTINCT visitor), count(*) FROM events WHERE day>=? AND {VIEWS} GROUP BY day", (since,))}
    series = [{'day': d, 'visitors': daily.get(d, [0, 0])[0], 'views': daily.get(d, [0, 0])[1]}
              for d in ((now - timedelta(days=n)).strftime('%Y-%m-%d') for n in range(days - 1, -1, -1))]

    def table(sql):
        return [{'name': name, 'visitors': n} for name, n in db.execute(sql, (since,)).fetchall()]

    return {
        'generated': now.isoformat(timespec='seconds'), 'days': days, 'since': since,
        'visitors': funnel[0]['count'], 'previous_visitors': funnel[0]['previous'],
        'page_views': views(since), 'previous_page_views': views(before, since),
        'funnel': funnel, 'series': series,
        'today': {'visitors': count(VIEWS, 'visitor', now.strftime('%Y-%m-%d')), 'views': views(now.strftime('%Y-%m-%d'))},
        'exports': [{'name': d or '?', 'count': n} for d, n in db.execute(
            "SELECT detail, count(*) FROM events WHERE day>=? AND name='export' GROUP BY detail", (since,)).fetchall()],
        'pages': table(f"SELECT path, count(DISTINCT day || visitor) n FROM events WHERE day>=? AND {VIEWS} GROUP BY path ORDER BY n DESC LIMIT 12"),
        'sources': table(f"SELECT source, count(DISTINCT day || visitor) n FROM events WHERE day>=? AND {VIEWS} AND source IS NOT NULL GROUP BY source ORDER BY n DESC LIMIT 15"),
    }


if __name__ == '__main__':
    from .app import connect, init_db
    init_db()
    with connect() as connection:
        print(report(connection, int(sys.argv[1]) if len(sys.argv) > 1 else 30))
