import io
import json
import logging
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, Form
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from PIL import UnidentifiedImageError, Image
from .pipeline import prepare_image, render, load_scene
from .sample import create_sample
from .steps import detect_panels, fallback_layout, prepare_steps, original_path, four_step_reading_order
from .enhance import clean_background
from . import accounts, billing, gallery

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
        db.execute("UPDATE jobs SET status='failed', error='The server restarted. Please export again.' WHERE status IN ('queued','rendering')")


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
    yield
    executor.shutdown(wait=True)


app = FastAPI(title='Strokeberry', lifespan=lifespan)


def current_user(request: Request):
    """The signed-in user (created on first visit). See accounts.py for the sign-in modes."""
    user_id, email, name, guest = accounts.identify(request)
    if DB not in _initialised:  # tables exist even when the app starts without its lifespan (tests)
        init_db()
        _initialised.add(DB)
    with connect() as db:
        return accounts.ensure_user(db, user_id, email, name, guest)


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
    return {'url': billing.create_checkout(user, body.interval)}


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
    with connect() as db:
        billing.apply_webhook(db, billing.parse(raw))
    return {'ok': True}


@app.get('/api/library')
def library():
    return gallery.items()


@app.post('/api/library/{item_id}/use', status_code=201)
def use_library_item(item_id: str, user=Depends(current_user)):
    item, path = gallery.find(item_id)
    project = add_project(path, item['title'], user)
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
    ratio: Literal['16:9', '9:16', '1:1'] = '16:9'
    resolution: Literal['720p', '1080p'] = '720p'
    color: bool = True
    pen: bool = True


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


def add_project(raw, name, user):
    if accounts.plan_id(user) == 'guest':
        with connect() as db:
            made = db.execute('SELECT count(*) FROM projects WHERE user_id=?', (user['id'],)).fetchone()[0]
        if made >= accounts.GUEST_PROJECT_LIMIT:
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
        db.execute('INSERT INTO projects (id, name, created, strokes, user_id) VALUES (?,?,?,?,?)',
                   (project_id, name[:100], datetime.now(timezone.utc).isoformat(), scene['strokes'], user['id']))
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


@app.post('/api/sample')
def sample(user=Depends(current_user)):
    with connect() as db:
        row = db.execute("SELECT id FROM projects WHERE name='A little bit of sunshine' AND user_id=? LIMIT 1",
                         (user['id'],)).fetchone()
    if row:
        return project_detail(row['id'], user)
    sample_path = DATA / 'botanical.png'
    if not sample_path.exists():
        create_sample(sample_path)
    return add_project(sample_path, 'A little bit of sunshine', user)


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


def run_job(job_id, project_id, settings):
    def update(progress, stage):
        with connect() as db:
            db.execute('UPDATE jobs SET progress=?, stage=?, status=? WHERE id=?',
                       (progress, stage, 'completed' if progress == 100 else 'rendering', job_id))
    try:
        update(2, 'Preparing your canvas')
        render(DATA / project_id, settings, update, DATA / project_id / f'{job_id}.mp4')
    except Exception:
        logging.exception('Render failed: %s', job_id)
        with connect() as db:
            db.execute("UPDATE jobs SET status='failed', error=? WHERE id=?", ('Rendering failed. Check the server log and confirm FFmpeg is installed, then try again.', job_id))


@app.post('/api/projects/{project_id}/jobs', status_code=202)
def export(project_id: str, settings: Settings, user=Depends(current_user)):
    get_project(project_id, user)
    with queue_lock, connect() as db:
        plan = accounts.check_export_allowed(db, user, settings.model_dump())
        mine = db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','rendering') AND user_id=?", (user['id'],)).fetchone()[0]
        if mine >= 2:
            raise HTTPException(429, 'You already have two videos rendering. Please wait for one to finish.')
        count = db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','rendering')").fetchone()[0]
        if count >= 8:
            raise HTTPException(429, 'The render queue is full. Please wait for an export to finish.')
        job_id = uuid.uuid4().hex
        # The watermark is decided by the server from the plan, never by the request.
        job_settings = dict(settings.model_dump(), watermark=plan['watermark'])
        db.execute('INSERT INTO jobs (id, project_id, status, progress, stage, settings, created, error, user_id) VALUES (?,?,?,?,?,?,?,?,?)',
                   (job_id, project_id, 'queued', 0, 'Waiting in the render queue', json.dumps(job_settings),
                    datetime.now(timezone.utc).isoformat(), None, user['id']))
        db.commit()
        executor.submit(run_job, job_id, project_id, job_settings)
    return job(job_id, user)


@app.get('/api/jobs/{job_id}')
def job(job_id: str, user=Depends(current_user)):
    with connect() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row or row['user_id'] != user['id']:
        raise HTTPException(404, 'Export not found.')
    item = dict(row)
    item.pop('user_id', None)
    item['settings'] = json.loads(item['settings'])
    if item['status'] == 'completed':
        item['url'] = signed(f"/api/jobs/{job_id}/download")
    return item


@app.get('/api/jobs')
def jobs(user=Depends(current_user)):
    with connect() as db:
        rows = db.execute('SELECT id FROM jobs WHERE user_id=? ORDER BY created DESC LIMIT 50', (user['id'],)).fetchall()
    return [job(row['id'], user) for row in rows]


@app.get('/api/jobs/{job_id}/download')
def download(job_id: str, e: str = None, s: str = None):
    # Opened by <video>/<a download>, so it's authorised by the link's signature rather than a header.
    accounts.verify_signature(DATA, f'/api/jobs/{job_id}/download', e, s)
    with connect() as db:
        row = db.execute('SELECT project_id, status FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Export not found.')
    if row['status'] != 'completed':
        raise HTTPException(409, 'Your video is not ready yet.')
    return FileResponse(DATA / row['project_id'] / f'{job_id}.mp4', media_type='video/mp4', filename=f'strokeberry-{job_id[:8]}.mp4')


if (ROOT / 'dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'dist', html=True), name='frontend')
