import io
import json
import logging
import shutil
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, Form
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field, model_validator
from PIL import UnidentifiedImageError, Image
from .pipeline import prepare_image, render, load_scene
from .sample import create_sample
from .steps import detect_panels, fallback_layout, prepare_steps, original_path, four_step_reading_order
from .enhance import clean_background
from . import accounts, analytics, billing, brand, gallery, mailer
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
DB = DATA / 'studio.sqlite'
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='renderer')
queue_lock = threading.Lock()


def connect():
    connection = sqlite3.connect(DB, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with connect() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, created TEXT, strokes INTEGER);
        CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, project_id TEXT, status TEXT, progress INTEGER, stage TEXT, settings TEXT, created TEXT, error TEXT);''')
        accounts.init_accounts(db)
        analytics.init(db)
        if 'origin' not in {row[1] for row in db.execute('PRAGMA table_info(projects)')}:
            # 'upload' (the visitor's own image) or 'example' (the welcome sample and library examples)
            db.execute("ALTER TABLE projects ADD COLUMN origin TEXT NOT NULL DEFAULT 'upload'")


def resume_interrupted_jobs():
    """Exports that were waiting or rendering when the server stopped are queued again and rendered from the start, so a
    restart or deploy never costs anyone a video. Only exports whose project has gone are failed (and pack videos refunded)."""
    with connect() as db:
        rows = db.execute("SELECT id, project_id, settings FROM jobs WHERE status IN ('queued','rendering') ORDER BY created").fetchall()
        gone = [row['id'] for row in rows if not (DATA / row['project_id']).exists()]
        if gone:
            db.execute(f"UPDATE jobs SET status='failed', error='The project was removed. Please export again.' WHERE id IN ({','.join('?' * len(gone))})", gone)
            accounts.refund_failed(db, gone)
        resumed = [row for row in rows if row['id'] not in gone]
        for row in resumed:
            db.execute("UPDATE jobs SET status='queued', progress=0, stage='Waiting in the render queue' WHERE id=?", (row['id'],))
    for row in resumed:
        executor.submit(run_job, row['id'], row['project_id'], json.loads(row['settings']))
    return len(resumed)


_initialised = set()  # databases whose tables were created in this process


def load_env_file(path=ROOT / '.env.local'):
    """Read KEY=value lines from .env.local without overriding variables that are already set."""
    import os
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        key, sep, value = line.strip().partition('=')
        if sep and key and not key.startswith('#'):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@asynccontextmanager
async def lifespan(app):
    load_env_file()
    init_db()
    _initialised.add(DB)
    resumed = resume_interrupted_jobs()
    if resumed:
        logging.info('Resumed %s interrupted export(s)', resumed)
    yield
    # Don't hold a restart hostage to a long render: unfinished exports are resumed when the server comes back.
    executor.shutdown(wait=False, cancel_futures=True)


# No public API docs in production: the API is only for the studio.
app = FastAPI(title='Strokeberry', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

SECURITY_HEADERS = {
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'X-Frame-Options': 'SAMEORIGIN',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
}


@app.middleware('http')
async def site_policies(request: Request, call_next):
    """One address for the site (www redirects to the bare domain, which search engines treat as canonical) and the
    browser security headers on every response."""
    host = request.headers.get('host', '')
    if host.startswith('www.'):
        query = f'?{request.url.query}' if request.url.query else ''
        return RedirectResponse(f'https://{host[4:]}{request.url.path}{query}', status_code=301)
    response = await call_next(request)
    if analytics.is_page_view(request, response.status_code):
        await run_in_threadpool(count_page_view, request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


def count_page_view(request):
    with connect() as db:
        analytics.record(db, 'pageview', request)


@app.exception_handler(StarletteHTTPException)
async def not_found_page(request: Request, exc: StarletteHTTPException):
    """A branded page for missing pages; the API keeps its JSON errors."""
    page = ROOT / 'dist' / '404.html'
    if exc.status_code == 404 and not request.url.path.startswith(('/api/', '/media/')) and page.exists():
        return HTMLResponse(page.read_text(), status_code=404)
    return await http_exception_handler(request, exc)


def current_user(request: Request):
    """The signed-in user (created on first visit). See accounts.py for the sign-in modes."""
    user_id, email, name, guest = accounts.identify(request)
    if DB not in _initialised:  # tables exist even when the app starts without its lifespan (tests)
        init_db()
        _initialised.add(DB)
    with connect() as db:
        user = accounts.ensure_user(db, user_id, email, name, guest)
        if not guest and user.get('email') and mark_notice(db, user, 'welcome'):
            mailer.welcome(user['email'], user.get('name'))
        return user


def mark_notice(db, user, key):
    """Remember that an email was sent so it's never sent twice. Returns True only for the request that recorded it."""
    before = user.get('notices') or '[]'
    seen = json.loads(before)
    if key in seen:
        return False
    after = json.dumps(seen + [key])
    # Compare-and-swap: if a simultaneous request recorded a notice first, this update matches nothing and we don't send.
    if not db.execute('UPDATE users SET notices=? WHERE id=? AND notices=?', (after, user['id'], before)).rowcount:
        return False
    user['notices'] = after
    return True


def signed(path):
    return accounts.sign_url(DATA, path)


@app.get('/api/me')
def me(user=Depends(current_user)):
    with connect() as db:
        return accounts.account_summary(db, user)


class CheckoutRequest(BaseModel):
    interval: Literal['month', 'year'] = 'month'


@app.post('/api/billing/checkout')
def checkout(body: CheckoutRequest = CheckoutRequest(), user=Depends(current_user)):
    if accounts.plan_id(user) == 'guest':
        raise HTTPException(401, 'Create a free account first, then upgrade.')
    url = billing.create_checkout(user, body.interval)
    with connect() as db:
        analytics.record(db, 'checkout', user=user, detail=body.interval)
    return {'url': url}


class PackRequest(BaseModel):
    pack: Literal['5', '15', '40']


@app.post('/api/billing/pack')
def pack_checkout(body: PackRequest, user=Depends(current_user)):
    if accounts.plan_id(user) == 'guest':
        raise HTTPException(401, 'Create a free account first, then get a video pack.')
    url = billing.create_pack_checkout(user, body.pack)
    with connect() as db:
        analytics.record(db, 'checkout', user=user, detail=f'pack-{body.pack}')
    return {'url': url}


@app.get('/api/offer')
def offer():
    """Public: the Founding member offer for the landing page (null when it isn't running)."""
    return {'founder': billing.founder_offer(), 'monthly': billing.price('month'), 'yearly': billing.price('year')}


@app.get('/api/billing/portal')
def billing_portal(user=Depends(current_user)):
    return {'url': billing.portal_url(user)}


@app.post('/api/billing/webhook')
async def billing_webhook(request: Request):
    raw = await request.body()
    billing.verify_webhook(raw, request.headers.get('X-Signature', ''))
    payload = billing.parse(raw)
    with connect() as db:
        user_id = billing.apply_webhook(db, payload)
        event = payload.get('meta', {}).get('event_name', '')
        if user_id and event in ('subscription_created', 'order_created'):
            paid = 'pack' if event == 'order_created' else (payload.get('data', {}).get('attributes', {}).get('variant_name') or 'pro')
            analytics.record(db, 'paid', user={'id': user_id}, detail=paid)
    return {'ok': True}


class Event(BaseModel):
    name: str = Field(max_length=40)


@app.post('/api/event')
def client_event(body: Event, request: Request, user=Depends(current_user)):
    """A few studio moments the server can't see itself (like the upgrade dialog opening). Unknown names are ignored."""
    if body.name in analytics.CLIENT_EVENTS:
        with connect() as db:
            analytics.record(db, body.name, request, user=user, path='/studio/')
    return {'ok': True}


@app.get('/api/library')
def library():
    return gallery.items()


@app.post('/api/library/{item_id}/use', status_code=201)
def use_library_item(item_id: str, user=Depends(current_user)):
    item, path = gallery.find(item_id)
    project = add_project(path, item['title'], user, origin='example')
    project['tutorial'] = bool(item.get('tutorial'))
    if project['tutorial']:  # step-by-step examples are 2×2 sheets, even when the panels can't be detected
        (DATA / project['id'] / 'layout-hint.json').write_text(json.dumps({'columns': 2, 'rows': 2}))
    return project


@app.post('/api/images/clean-background')
def enhance_image(file: UploadFile, strength: int = Form(default=50, ge=0, le=100), user=Depends(current_user)):
    if accounts.plan_id(user) == 'guest':
        raise HTTPException(401, 'Create a free account to use image cleanup.')
    raw=file.file.read(15*1024*1024+1)
    if len(raw)>15*1024*1024:
        raise HTTPException(413,'Please choose an image smaller than 15 MB.')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.width*image.height>20_000_000:
                raise HTTPException(400,'Please choose an image with at most 20 million pixels.')
            cleaned=clean_background(image,strength)
        output=io.BytesIO();cleaned.save(output,format='PNG')
        return Response(output.getvalue(),media_type='image/png',headers={'Cache-Control':'no-store'})
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):
        raise HTTPException(400,'Use a valid PNG, JPG, or WebP image.')


@app.get('/media/{project_id}/{filename}')
def media(project_id: str, filename: str, e: str = None, s: str = None):
    # <img> tags can't send sign-in headers, so media links carry an expiring signature instead.
    accounts.verify_signature(DATA, f'/media/{project_id}/{filename}', e, s)
    get_project(project_id)
    allowed = {'source.png', 'reveal.png', 'original.png'} | {f'{prefix}-{i}.png' for prefix in ('step', 'rank') for i in range(8)}
    if filename not in allowed:
        raise HTTPException(404, 'Image not found.')
    path = original_path(DATA / project_id) if filename == 'original.png' else DATA / project_id / filename
    if not path.exists():
        raise HTTPException(404, 'Image not found.')
    return FileResponse(path)



class Settings(BaseModel):
    style: Literal['pencil', 'ink'] = 'pencil'
    duration: int = Field(default=15, ge=5, le=300)
    ratio: Literal['16:9', '9:16', '1:1', '4:5', 'auto'] = '16:9'
    resolution: Literal['720p', '1080p', '4k'] = '1080p'
    color: bool = True
    pen: bool = True
    hand: Literal['pencil', 'light', 'medium', 'dark'] = 'pencil'  # what draws: a plain pencil, or a hand in a skin tone
    canvas: Literal['paper', 'blackboard', 'greenboard'] = 'paper'


class Crop(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=.02, le=1)
    height: float = Field(ge=.02, le=1)

    @model_validator(mode='after')
    def fits(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError('Keep the crop inside the image.')
        return self


class DrawingStage(BaseModel):
    crop: Crop
    label: str = Field(min_length=1, max_length=40)
    seconds: int = Field(ge=1, le=300)
    offset_x: float = Field(default=0, ge=-25, le=25)
    offset_y: float = Field(default=0, ge=-25, le=25)
    scale: float = Field(default=1, ge=.7, le=1.3)


class StepConfig(BaseModel):
    stages: list[DrawingStage] = Field(min_length=1, max_length=8)
    align: bool = True

    @model_validator(mode='after')
    def duration_fits(self):
        if not 5 <= sum(s.seconds for s in self.stages) <= 300:
            raise ValueError('Total stage timing must be between 5 seconds and 5 minutes.')
        return self


def get_project(project_id, user=None):
    with connect() as db:
        row = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    # Another user's project is reported as missing rather than forbidden, so ids can't be probed.
    if not row or (user is not None and row['user_id'] != user['id']):
        raise HTTPException(404, 'Project not found.')
    return dict(row)


def project_detail(project_id, user=None):
    project = get_project(project_id, user)
    project.update(load_scene(DATA / project_id))
    with connect() as db:
        db.execute('UPDATE projects SET strokes=? WHERE id=?', (project['strokes'], project_id))
    project['original'] = signed(f'/media/{project_id}/original.png')
    for stage in project.get('stages', []):
        stage['source'] = signed(f"/media/{project_id}/{stage['image']}")
        stage['reveal'] = signed(f"/media/{project_id}/{stage['rank']}")
    project['source'] = signed(f'/media/{project_id}/source.png')
    project['reveal'] = signed(f'/media/{project_id}/reveal.png')
    project.pop('user_id', None)
    return project


GUEST_EXAMPLE_LIMIT = 20  # examples a guest may open (each one is prepared on the server)


def add_project(raw, name, user, origin='upload'):
    """Prepare an image as a new project. A guest's limit counts only their own uploads, so browsing the welcome sample
    and the examples never uses it up; reopening an example a guest already has returns that copy."""
    if accounts.plan_id(user) == 'guest':
        with connect() as db:
            if origin == 'example':
                row = db.execute("SELECT id FROM projects WHERE user_id=? AND origin='example' AND name=? ORDER BY created LIMIT 1",
                                 (user['id'], name[:100])).fetchone()
                if row:
                    return project_detail(row['id'], user)
            made = db.execute('SELECT count(*) FROM projects WHERE user_id=? AND origin=?', (user['id'], origin)).fetchone()[0]
        limit = GUEST_EXAMPLE_LIMIT if origin == 'example' else accounts.GUEST_PROJECT_LIMIT
        if made >= limit:
            raise HTTPException(401, 'Create a free account to keep making projects.')
    project_id = uuid.uuid4().hex
    folder = DATA / project_id
    folder.mkdir()
    try:
        scene = prepare_image(raw, folder)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        import shutil
        shutil.rmtree(folder)
        raise HTTPException(400, str(exc) if isinstance(exc, ValueError) else 'Use a valid PNG, JPG, or WebP image.')
    with connect() as db:
        db.execute('INSERT INTO projects (id, name, created, strokes, user_id, origin) VALUES (?,?,?,?,?,?)',
                   (project_id, name[:100], datetime.now(timezone.utc).isoformat(), scene['strokes'], user['id'], origin))
        analytics.record(db, 'project', user=user, detail=origin)
    return project_detail(project_id, user)


@app.get('/api/health')
def health():
    import shutil
    import os
    return {'status': 'ok', 'encoder': bool(os.environ.get('FFMPEG_PATH') or shutil.which('ffmpeg'))}


@app.get('/api/projects')
def projects(user=Depends(current_user)):
    with connect() as db:
        rows = db.execute('SELECT id, name, created, strokes FROM projects WHERE user_id=? ORDER BY created DESC',
                          (user['id'],)).fetchall()
    return [dict(row, source=signed(f"/media/{row['id']}/source.png")) for row in rows]


@app.post('/api/projects', status_code=201)
def upload(file: UploadFile, user=Depends(current_user)):
    raw = file.file.read(15 * 1024 * 1024 + 1)
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, 'Please choose an image smaller than 15 MB.')
    return add_project(io.BytesIO(raw), Path(file.filename or 'Untitled').stem, user)


SAMPLE_NAME = 'Sweet cupcake'
SAMPLE_LIBRARY_ID = 'food-01-cupcake'
OLD_SAMPLE_NAME = 'A little bit of sunshine'  # the previous starter project, still recognised for existing users


@app.post('/api/sample')
def sample(user=Depends(current_user)):
    """The starter project a new visitor sees: a bold, colourful cupcake from the example library."""
    with connect() as db:
        row = db.execute('SELECT id FROM projects WHERE name IN (?, ?) AND user_id=? ORDER BY created LIMIT 1',
                         (SAMPLE_NAME, OLD_SAMPLE_NAME, user['id'])).fetchone()
    if row:
        return project_detail(row['id'], user)
    try:
        _, path = gallery.find(SAMPLE_LIBRARY_ID)
        return add_project(path, SAMPLE_NAME, user, origin='example')
    except HTTPException:  # the example library isn't installed: fall back to the drawn botanical starter
        sample_path = DATA / 'botanical.png'
        if not sample_path.exists():
            create_sample(sample_path)
        return add_project(sample_path, OLD_SAMPLE_NAME, user, origin='example')


@app.get('/api/projects/{project_id}')
def detail(project_id: str, user=Depends(current_user)):
    return project_detail(project_id, user)


@app.get('/api/projects/{project_id}/step-layout')
def step_layout(project_id: str, user=Depends(current_user)):
    project = project_detail(project_id, user)
    layout = detect_panels(DATA / project_id)
    hint = DATA / project_id / 'layout-hint.json'
    if not layout['detected'] and hint.exists():  # a gallery tutorial sheet whose grid we already know
        grid = json.loads(hint.read_text())
        layout = fallback_layout(layout['width'], layout['height'], grid['columns'], grid['rows'])
    return dict(layout, config=project.get('config'))


@app.post('/api/projects/{project_id}/steps', status_code=201)
def create_steps(project_id: str, config: StepConfig, user=Depends(current_user)):
    parent = get_project(project_id, user)
    accounts.check_duration(user, sum(stage.seconds for stage in config.stages))
    config_data = config.model_dump()
    config_data['stages'] = four_step_reading_order(config_data['stages'])
    derived_id = uuid.uuid4().hex
    folder = DATA / derived_id
    folder.mkdir()
    try:
        scene = prepare_steps(DATA / project_id, folder, config_data)
        with connect() as db:
            db.execute('INSERT INTO projects (id, name, created, strokes, user_id) VALUES (?,?,?,?,?)',
                       (derived_id, (parent['name'].removesuffix(' · steps') + ' · steps')[:100],
                        datetime.now(timezone.utc).isoformat(), scene['strokes'], user['id']))
    except Exception:
        import shutil
        shutil.rmtree(folder)
        logging.exception('Could not prepare drawing steps')
        raise HTTPException(500, 'Could not align these steps. Check your crops and try again.')
    return project_detail(derived_id, user)


def notify_allowance(job_id):
    """After a Free user's export finishes, tell them when they are down to one video and when they've used all three."""
    try:
        with connect() as db:
            row = db.execute('SELECT user_id FROM jobs WHERE id=?', (job_id,)).fetchone()
            user = row and db.execute('SELECT * FROM users WHERE id=?', (row['user_id'],)).fetchone()
            if not user or not user['email'] or accounts.plan_id(dict(user)) != 'free':
                return
            user = dict(user)
            used = accounts.usage(db, user)
            remaining = used['remaining']
            month = datetime.now(timezone.utc).strftime('%Y-%m')  # one notice of each kind per month, since the allowance renews
            if remaining <= 1 and mark_notice(db, user, f'allowance-{remaining}-{month}'):
                mailer.allowance(user['email'], remaining, accounts.short_date(used['resets']) if used['resets'] else None)
    except Exception:
        logging.exception('Allowance notice failed')


def run_job(job_id, project_id, settings):
    def update(progress, stage):
        with connect() as db:
            db.execute('UPDATE jobs SET progress=?, stage=?, status=? WHERE id=?',
                       (progress, stage, 'completed' if progress == 100 else 'rendering', job_id))
    try:
        update(2, 'Preparing your canvas')
        render(DATA / project_id, settings, update, DATA / project_id / f'{job_id}.mp4')
        notify_allowance(job_id)
    except Exception:
        logging.exception('Render failed: %s', job_id)
        with connect() as db:
            db.execute("UPDATE jobs SET status='failed', error=? WHERE id=?", ('Rendering failed. Check the server log and confirm FFmpeg is installed, then try again.', job_id))
            accounts.refund_failed(db, [job_id])


def check_capacity(db, user, extra=1):
    """Cap how many exports one person can have waiting or rendering (Free 2, Pro 9), and the whole queue."""
    limit = accounts.ACTIVE_RENDERS['pro' if accounts.plan_id(user) == 'pro' else 'free']
    mine = db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','rendering') AND user_id=?", (user['id'],)).fetchone()[0]
    if mine + extra > limit:
        raise HTTPException(429, 'You already have %s rendering. Please wait for one to finish.' % ('two videos' if limit == 2 else 'the maximum number of videos'))
    count = db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','rendering')").fetchone()[0]
    if count + extra > 30:
        raise HTTPException(429, 'The render queue is full. Please wait for an export to finish.')


def brand_for_export(db, user):
    """A Pro member's brand kit, as extra render settings (empty for everyone else)."""
    row = db.execute('SELECT * FROM brand_kits WHERE user_id=?', (user['id'],)).fetchone()
    if not row or not row['enabled'] or accounts.plan_id(user) != 'pro':
        return {}
    extra = {}
    if row['ink_color']:
        extra['ink_color'] = row['ink_color']
    path = brand.logo_path(DATA, user['id'])
    if row['has_logo'] and path.exists():
        extra.update(logo=str(path), logo_corner=row['logo_corner'] or 'bottom-right')
    return extra


def enqueue(db, user, plan, project_id, settings):
    """Insert an export job and hand it to the renderer. The caller has already checked the plan and capacity."""
    job_id = uuid.uuid4().hex
    # The watermark, end card and brand kit are decided by the server from the plan, never by the request.
    job_settings = dict(settings, watermark=plan['watermark'], end_card=plan['watermark'], **brand_for_export(db, user))
    accounts.spend(db, user, plan)
    db.execute('INSERT INTO jobs (id, project_id, status, progress, stage, settings, created, error, user_id, paid_with) VALUES (?,?,?,?,?,?,?,?,?,?)',
               (job_id, project_id, 'queued', 0, 'Waiting in the render queue', json.dumps(job_settings),
                datetime.now(timezone.utc).isoformat(), None, user['id'], plan.get('paid_with', 'plan')))
    analytics.record(db, 'export', user=user, detail='pack' if plan.get('paid_with') == 'pack' else accounts.plan_id(user))
    db.commit()
    executor.submit(run_job, job_id, project_id, job_settings)
    return job_id


@app.post('/api/projects/{project_id}/jobs', status_code=202)
def export(project_id: str, settings: Settings, user=Depends(current_user)):
    get_project(project_id, user)
    with queue_lock, connect() as db:
        plan = accounts.check_export_allowed(db, user, settings.model_dump())
        check_capacity(db, user)
        job_id = enqueue(db, user, plan, project_id, settings.model_dump())
    return job(job_id, user)


class BatchRequest(BaseModel):
    project_ids: list[str] = Field(min_length=1, max_length=6)
    ratios: list[Literal['16:9', '9:16', '1:1', '4:5', 'auto']] = Field(min_length=1, max_length=5)
    settings: Settings = Settings()


@app.post('/api/batch', status_code=202)
def batch_export(body: BatchRequest, user=Depends(current_user)):
    """Pro: export several projects and/or several formats in one go."""
    if accounts.plan_id(user) == 'guest':
        raise HTTPException(401, 'Create a free account to export your video. It takes a few seconds.')
    if accounts.plan_id(user) != 'pro':
        raise HTTPException(402, 'Batch export is part of Pro.')
    ids, ratios = list(dict.fromkeys(body.project_ids)), list(dict.fromkeys(body.ratios))
    for project_id in ids:
        get_project(project_id, user)
    total = len(ids) * len(ratios)
    with queue_lock, connect() as db:
        plan = accounts.check_export_allowed(db, user, body.settings.model_dump())
        if plan['paid_with'] != 'plan' or accounts.usage(db, user)['remaining'] < total:
            raise HTTPException(429, 'That would go over this month’s export limit. Choose fewer videos or formats.')
        check_capacity(db, user, total)
        made = [enqueue(db, user, plan, project_id, dict(body.settings.model_dump(), ratio=ratio))
                for project_id in ids for ratio in ratios]
    return [job(job_id, user) for job_id in made]


@app.delete('/api/jobs/{job_id}', status_code=204)
def delete_job(job_id: str, user=Depends(current_user)):
    with connect() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=? AND user_id=?', (job_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Export not found.')
        if row['status'] in ('queued', 'rendering'):
            raise HTTPException(409, 'This video is still rendering.')
        # Kept as 'deleted' so a removed video still counts towards the month's allowance.
        db.execute("UPDATE jobs SET status='deleted' WHERE id=?", (job_id,))
    for suffix in ('.mp4', '.log', '.partial.mp4'):
        (DATA / row['project_id'] / f'{job_id}{suffix}').unlink(missing_ok=True)


@app.get('/api/jobs/{job_id}')
def job(job_id: str, user=Depends(current_user)):
    with connect() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row or row['user_id'] != user['id'] or row['status'] == 'deleted':
        raise HTTPException(404, 'Export not found.')
    item = dict(row)
    item.pop('user_id', None)
    item['settings'] = {k: v for k, v in json.loads(item['settings']).items() if k not in ('logo', 'logo_corner')}
    if item['status'] == 'completed':
        item['url'] = signed(f"/api/jobs/{job_id}/download")
    return item


@app.get('/api/jobs')
def jobs(user=Depends(current_user)):
    with connect() as db:
        rows = db.execute("SELECT id FROM jobs WHERE user_id=? AND status != 'deleted' ORDER BY created DESC LIMIT 50", (user['id'],)).fetchall()
    return [job(row['id'], user) for row in rows]


@app.get('/api/jobs/{job_id}/download')
def download(job_id: str, e: str = None, s: str = None):
    # Opened by <video>/<a download>, so it's authorised by the link's signature rather than a header.
    accounts.verify_signature(DATA, f'/api/jobs/{job_id}/download', e, s)
    with connect() as db:
        row = db.execute('SELECT project_id, status FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Export not found.')
    if row['status'] == 'deleted':
        raise HTTPException(404, 'Export not found.')
    if row['status'] != 'completed':
        raise HTTPException(409, 'Your video is not ready yet.')
    return FileResponse(DATA / row['project_id'] / f'{job_id}.mp4', media_type='video/mp4', filename=f'strokeberry-{job_id[:8]}.mp4')


class ProjectName(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@app.patch('/api/projects/{project_id}')
def rename_project(project_id: str, body: ProjectName, user=Depends(current_user)):
    get_project(project_id, user)
    with connect() as db:
        db.execute('UPDATE projects SET name=? WHERE id=?', (body.name.strip() or 'Untitled', project_id))
    return project_detail(project_id, user)


class EnhanceBody(BaseModel):
    accept: bool


@app.post('/api/projects/{project_id}/enhance')
def enhance_project(project_id: str, body: EnhanceBody, user=Depends(current_user)):
    """Accept or decline the suggested extra lines; the drawing is re-prepared with or without them."""
    get_project(project_id, user)
    folder = DATA / project_id
    if not load_scene(folder).get('enhance'):
        raise HTTPException(409, 'There are no suggested lines for this image.')
    (folder / 'enhance.json').write_text(json.dumps({'state': 'accepted' if body.accept else 'rejected'}))
    prepare_image(folder / 'source.png', folder)
    return project_detail(project_id, user)


@app.post('/api/projects/{project_id}/duplicate', status_code=201)
def duplicate_project(project_id: str, user=Depends(current_user)):
    original = get_project(project_id, user)
    if accounts.plan_id(user) == 'guest':
        with connect() as db:
            made = db.execute("SELECT count(*) FROM projects WHERE user_id=? AND origin='upload'", (user['id'],)).fetchone()[0]
        if made >= accounts.GUEST_PROJECT_LIMIT:
            raise HTTPException(401, 'Create a free account to keep making projects.')
    new_id = uuid.uuid4().hex
    shutil.copytree(DATA / project_id, DATA / new_id, ignore=shutil.ignore_patterns('*.mp4', '*.log'))
    with connect() as db:
        db.execute('INSERT INTO projects (id, name, created, strokes, user_id) VALUES (?,?,?,?,?)',
                   (new_id, f"{original['name']} copy"[:100], datetime.now(timezone.utc).isoformat(), original['strokes'], user['id']))
    return project_detail(new_id, user)


@app.delete('/api/projects/{project_id}', status_code=204)
def delete_project(project_id: str, user=Depends(current_user)):
    get_project(project_id, user)
    with connect() as db:
        busy = db.execute("SELECT count(*) FROM jobs WHERE project_id=? AND status IN ('queued','rendering')", (project_id,)).fetchone()[0]
        if busy:
            raise HTTPException(409, 'A video from this project is still rendering. Try again in a moment.')
        db.execute("UPDATE jobs SET status='deleted' WHERE project_id=?", (project_id,))
        db.execute('DELETE FROM projects WHERE id=?', (project_id,))
    shutil.rmtree(DATA / project_id, ignore_errors=True)


# ------------------------------------------------------------------------------ saved styles (presets)

class PresetBody(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    settings: Settings


@app.get('/api/presets')
def list_presets(user=Depends(current_user)):
    with connect() as db:
        rows = db.execute('SELECT id, name, settings FROM presets WHERE user_id=? ORDER BY created', (user['id'],)).fetchall()
    return [{'id': row['id'], 'name': row['name'], 'settings': json.loads(row['settings'])} for row in rows]


@app.post('/api/presets', status_code=201)
def save_preset(body: PresetBody, user=Depends(current_user)):
    if accounts.plan_id(user) == 'guest':
        raise HTTPException(401, 'Create a free account to save your styles.')
    pro = accounts.plan_id(user) == 'pro'
    limit = accounts.PRO_PRESET_LIMIT if pro else accounts.FREE_PRESET_LIMIT
    name = body.name.strip()
    with connect() as db:
        existing = db.execute('SELECT id FROM presets WHERE user_id=? AND lower(name)=lower(?)', (user['id'], name)).fetchone()
        count = db.execute('SELECT count(*) FROM presets WHERE user_id=?', (user['id'],)).fetchone()[0]
        if not existing and count >= limit:
            raise HTTPException(402, f'You can save up to {limit} style{"s" if limit > 1 else ""}. ' +
                                ('Delete one to save another.' if pro else 'Pro lets you save up to 20.'))
        preset_id = existing['id'] if existing else uuid.uuid4().hex
        db.execute('INSERT OR REPLACE INTO presets (id, user_id, name, settings, created) VALUES (?,?,?,?,COALESCE((SELECT created FROM presets WHERE id=?),?))',
                   (preset_id, user['id'], name, body.settings.model_dump_json(), preset_id, datetime.now(timezone.utc).isoformat()))
    return {'id': preset_id, 'name': name, 'settings': body.settings.model_dump()}


@app.delete('/api/presets/{preset_id}', status_code=204)
def delete_preset(preset_id: str, user=Depends(current_user)):
    with connect() as db:
        gone = db.execute('DELETE FROM presets WHERE id=? AND user_id=?', (preset_id, user['id'])).rowcount
    if not gone:
        raise HTTPException(404, 'Style not found.')


# ------------------------------------------------------------------------------ brand kit (Pro)

class BrandBody(BaseModel):
    name: str = Field(default='', max_length=60)
    ink_color: str = ''
    logo_corner: Literal['bottom-right', 'bottom-left', 'top-right', 'top-left'] = 'bottom-right'
    enabled: bool = True

    @model_validator(mode='after')
    def colour(self):
        if self.ink_color and not brand.HEX.match(self.ink_color):
            raise ValueError('Choose a colour like #1b2c24.')
        return self


def brand_view(user):
    with connect() as db:
        row = db.execute('SELECT * FROM brand_kits WHERE user_id=?', (user['id'],)).fetchone()
    kit = {'name': '', 'ink_color': '', 'logo_corner': 'bottom-right', 'enabled': True, 'logo': None}
    if row:
        kit.update(name=row['name'] or '', ink_color=row['ink_color'] or '', logo_corner=row['logo_corner'] or 'bottom-right',
                   enabled=bool(row['enabled']))
        if row['has_logo'] and brand.logo_path(DATA, user['id']).exists():
            kit['logo'] = signed(f"/api/brand/logo/{user['id']}")
    kit['allowed'] = accounts.plan_id(user) == 'pro'
    return kit


def require_pro(user):
    if accounts.plan_id(user) == 'guest':
        raise HTTPException(401, 'Create a free account first.')
    if accounts.plan_id(user) != 'pro':
        raise HTTPException(402, 'The brand kit is part of Pro.')


@app.get('/api/brand')
def get_brand(user=Depends(current_user)):
    return brand_view(user)


@app.put('/api/brand')
def save_brand(body: BrandBody, user=Depends(current_user)):
    require_pro(user)
    with connect() as db:
        db.execute("""INSERT INTO brand_kits (user_id, name, ink_color, logo_corner, enabled) VALUES (?,?,?,?,?)
                      ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, ink_color=excluded.ink_color,
                      logo_corner=excluded.logo_corner, enabled=excluded.enabled""",
                   (user['id'], body.name.strip(), body.ink_color, body.logo_corner, int(body.enabled)))
    return brand_view(user)


@app.post('/api/brand/logo')
def upload_logo(file: UploadFile, user=Depends(current_user)):
    require_pro(user)
    raw = file.file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, 'Please choose a logo smaller than 5 MB.')
    try:
        brand.save_logo(DATA, user['id'], raw)
    except ValueError as error:
        raise HTTPException(400, str(error))
    with connect() as db:
        db.execute('INSERT INTO brand_kits (user_id, has_logo) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET has_logo=1', (user['id'],))
    return brand_view(user)


@app.delete('/api/brand/logo')
def remove_logo(user=Depends(current_user)):
    require_pro(user)
    brand.logo_path(DATA, user['id']).unlink(missing_ok=True)
    with connect() as db:
        db.execute('UPDATE brand_kits SET has_logo=0 WHERE user_id=?', (user['id'],))
    return brand_view(user)


@app.get('/api/brand/logo/{owner}')
def logo_file(owner: str, e: str = None, s: str = None):
    accounts.verify_signature(DATA, f'/api/brand/logo/{owner}', e, s)
    path = brand.logo_path(DATA, owner)
    if not path.exists():
        raise HTTPException(404, 'No logo.')
    return FileResponse(path, media_type='image/png')


@app.get('/api/ideas')
def ideas():
    """Three example suggestions that change every week, for the studio home."""
    year, week, _ = date.today().isocalendar()
    return list(gallery.ideas(year * 53 + week))


@app.api_route('/api/{rest:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], include_in_schema=False)
def unknown_api(rest: str):
    # Unknown API addresses get a JSON 404 (the site below would otherwise answer with its HTML "page not found").
    raise HTTPException(404, 'Not found.')


if (ROOT / 'dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'dist', html=True), name='frontend')
