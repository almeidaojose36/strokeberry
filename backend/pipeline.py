"""CPU contour tracing, nearest-endpoint ordering, and streaming MP4 rendering."""
import json
import math
import os
import shutil
import subprocess
import threading
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from . import watermark
from .brand import hex_to_rgb
from . import endcard, hands
from .linework import edge_strokes, extract_strokes, ink_mask, missing_lines
from .artistry import SCENE_VERSION, clean_paths, make_timeline, event_position, order_strokes, phase_bounds

_scene_lock = threading.Lock()

PAPER = (250, 249, 246)


def blend_white_background(rgb):
    """Turn a plain white background into the paper colour so the colour reveal blends into the canvas.

    Only near-white areas connected to the image border are changed, so whites inside the artwork (a panda's belly, the
    white of an eye) stay white. The edge is feathered a little so there is no halo around the drawing."""
    lightest = rgb.min(axis=2)
    count, labels = cv2.connectedComponents(np.uint8(lightest >= 238))
    if count < 2:
        return rgb
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    background = np.isin(labels, border[border > 0]).astype(np.uint8)
    if not background.any():
        return rgb
    reach = cv2.dilate(background, np.ones((5, 5), np.uint8)).astype(bool)
    weight = np.clip((lightest.astype(np.float32) - 215) / 35, 0, 1) * reach
    paper = np.array(PAPER, np.float32)
    return np.uint8(rgb * (1 - weight[..., None]) + paper * weight[..., None])


BRUSH_DEPTH = .06  # how far (as a share of the colour reveal) the bristle texture pushes the painted edge back and forth
PAINT_SAMPLES = 48
BOARDS = {'blackboard': (40, 44, 42), 'greenboard': (38, 76, 60)}
CHALK = (240, 240, 232)


def brush_texture(shape):
    """Fixed streaky noise (-.5..+.5): short horizontal bristle marks, so the colour edge looks brushed on."""
    height, width = shape
    rng = np.random.default_rng(7)
    coarse = rng.random((max(2, height // 3), max(2, width // 28))).astype(np.float32)
    streaks = cv2.resize(coarse, (width, height), interpolation=cv2.INTER_CUBIC)
    blotches = cv2.resize(rng.random((max(2, height // 40), max(2, width // 40))).astype(np.float32), (width, height),
                          interpolation=cv2.INTER_CUBIC)
    return np.clip(.65 * streaks + .35 * blotches, 0, 1) - .5


def paint_path(reveal, content):
    """Where the brush is while the colour comes in: for evenly spaced moments of the reveal, a point on the edge being
    painted, chosen close to the previous one so the hand glides instead of jumping. Returns [[x, y], ...] in source
    pixels (shared verbatim by the browser preview and the MP4 renderer)."""
    ranks = reveal.astype(np.float32)
    height, width = ranks.shape
    reach = .12 * np.hypot(width, height)
    points, previous = [], None
    for k in range(PAINT_SAMPLES):
        amount = (k + .5) / PAINT_SAMPLES
        front = content & (np.abs(ranks - (amount * 270 - 10)) < 12)
        ys, xs = np.nonzero(front)
        if len(xs):
            if previous is None:
                pick = int(np.argmin(xs + ys))
            else:
                pick = int(np.argmin((xs - previous[0]) ** 2 + (ys - previous[1]) ** 2))
            near = (xs - xs[pick]) ** 2 + (ys - ys[pick]) ** 2 < reach ** 2
            previous = (float(xs[near].mean()), float(ys[near].mean()))
        points.append([round(previous[0], 1), round(previous[1], 1)] if previous else None)
    known = [p for p in points if p]
    if not known:
        return []
    filled = []
    for p in points:  # moments with nothing visible to paint keep the last place (or the first known one)
        filled.append(p or (filled[-1] if filled else known[0]))
    smooth = [[round(float(np.mean([filled[j][i] for j in range(max(0, k - 2), min(len(filled), k + 3))])), 1)
               for i in (0, 1)] for k in range(len(filled))]
    return smooth


TRIM_PADDING = .07  # empty border kept around the artwork, as a share of its longer side


def trim_margins(image):
    """Crop away empty paper so the subject fills the frame. Idempotent: a second pass finds nothing left to trim."""
    rgb = np.array(image)
    ink = np.abs(rgb.astype(np.int16) - np.array(PAPER, np.int16)).sum(axis=2) > 40
    ink = cv2.morphologyEx(np.uint8(ink), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0  # ignore specks and dust
    rows, cols = np.where(ink.any(axis=1))[0], np.where(ink.any(axis=0))[0]
    if not len(rows) or not len(cols):
        return image
    top, bottom, left, right = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    if (bottom - top) * (right - left) < .02 * ink.size:
        return image  # too little to frame (a blank or nearly blank picture)
    pad = round(TRIM_PADDING * max(bottom - top, right - left))
    box = (max(0, left - pad), max(0, top - pad), min(image.width, right + pad), min(image.height, bottom + pad))
    slack = (box[2] - box[0]) * (box[3] - box[1]) / (image.width * image.height)
    return image.crop(box) if slack < .94 else image  # only when it gains something worth having


def prepare_image(raw, folder: Path):
    with Image.open(raw) as image:
        if image.width * image.height > 20_000_000:
            raise ValueError('Please use an image with fewer than 20 megapixels.')
        image = ImageOps.exif_transpose(image)
        rgba = image.convert('RGBA')
        image = Image.new('RGBA', rgba.size, PAPER + (255,))
        image.alpha_composite(rgba)
        image = image.convert('RGB')
        if not (folder / 'original.png').exists():
            image.save(folder / 'original.png')
        image = trim_margins(Image.fromarray(blend_white_background(np.array(image))))  # original.png above stays untouched
        image.thumbnail((900, 900))
        image.save(folder / 'source.png')
    rgb = np.array(image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    outlines = extract_strokes(rgb)
    if outlines:
        paths, method = outlines[0], 'outlines'  # the artwork's own black lines, one centre line each
    else:
        paths, method = edge_strokes(rgb), 'edges'  # no usable outlines: trace the colour edges, as single lines
        if len(paths) < 4:  # nearly blank picture: the older contour tracing as a last resort
            edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 45, 125)
            contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=lambda c: cv2.arcLength(c, False), reverse=True)
            paths, method = clean_paths(contours, gray.shape), 'contours'
    # Lines the artwork lacks (fur tufts, tail tips...) are only suggested; the user accepts or keeps the original.
    suggested = missing_lines(rgb, paths, outlines[1]) if outlines else []
    state = None
    if (folder / 'enhance.json').exists():
        state = json.loads((folder / 'enhance.json').read_text()).get('state')
    if suggested and state == 'accepted':
        paths = list(paths) + suggested
    # Strokes are ordered like a person draws: major shapes first, then details, top to bottom (see artistry.order_strokes).
    ordered = [p.tolist() for p in order_strokes(paths, gray.shape[1], gray.shape[0])]
    # Deterministic color segmentation: median-cut palette, then region-by-region reveal.
    indexed = image.quantize(colors=9, method=Image.Quantize.MEDIANCUT)
    labels = np.array(indexed)
    palette = np.array(indexed.getpalette(), dtype=np.uint8).reshape(-1, 3)
    used = np.unique(labels)
    used = sorted(used, key=lambda k: float(palette[k].mean()))
    yy, xx = np.indices(labels.shape)
    sweep = (xx / max(1, image.width - 1) + yy / max(1, image.height - 1)) / 2
    ranks = np.zeros(labels.shape, dtype=np.float32)
    # Each colour gets a slice of the reveal proportional to how much it changes the picture, so the colour arrives steadily
    # across the whole reveal instead of finishing early (the last colours are often near-white and invisible). Dark to
    # light order is kept, and every colour gets at least a small slice so thin dark outlines still read as a step.
    distance = np.abs(rgb.astype(np.float32) - np.array(PAPER, np.float32)).sum(axis=2)
    weights = np.array([float(distance[labels == label].sum()) for label in used])
    if weights.sum() <= 0:
        weights = np.ones(len(used))
    weights = np.maximum(weights / weights.sum(), .03)
    edges = np.concatenate([[0.], np.cumsum(weights / weights.sum())])
    for i, label in enumerate(used):
        region = labels == label
        ranks[region] = edges[i] + (edges[i + 1] - edges[i]) * sweep[region] * .9
    ranks = np.clip(ranks + brush_texture(labels.shape) * BRUSH_DEPTH, 0, 1)  # a bristly, painted edge instead of a smooth wipe
    Image.fromarray(np.uint8(ranks * 245)).save(folder / 'reveal.png')
    scene = {'width': image.width, 'height': image.height, 'paths': ordered,
             'version': SCENE_VERSION, 'timeline': make_timeline(ordered),
             'paint_path': paint_path(np.uint8(ranks * 245), distance > 30),
             'strokes': len(ordered), 'line_method': method, 'line_width': round(float(outlines[1]), 2) if outlines else None,
             'enhance': {'state': state, 'count': len(suggested), 'lines': [np.round(np.array(x), 1).tolist() for x in suggested]} if suggested else None, 'palette': [palette[k].tolist() for k in used]}
    temporary = folder / 'scene.tmp'
    temporary.write_text(json.dumps(scene))
    temporary.replace(folder / 'scene.json')
    return scene


def load_scene(folder):
    # Existing projects acquire the new strokes automatically; exports stay intact.
    with _scene_lock:
        scene = json.loads((folder / 'scene.json').read_text())
        if scene.get('mode') == 'steps':
            from .steps import REVEAL_VERSION, prepare_steps
            if scene.get('reveal_version') != REVEAL_VERSION:
                scene = prepare_steps(folder, folder, scene['config'])
            return scene
        if scene.get('version') != SCENE_VERSION:
            scene = prepare_image(folder / 'source.png', folder)
        return scene


def pen_weight(line_width, unit_in_source):
    """How much heavier than the default the pen should draw so its line matches the artwork's own outline weight (about
    85% of it, since the colour reveal then lands on the same line). 1 when the weight is unknown or already fine."""
    if not line_width:
        return 1.
    return float(min(4., max(1., .85 * line_width / (unit_in_source * 1.45))))


def draw_mark(canvas, a, b, pressure, style, unit, tint=None, paper=PAPER):
    """Subpixel strokes preserve pressure changes at every export resolution."""
    pencil = style == 'pencil'
    opacity = (.35 + .45 * pressure) if pencil else (.65 + .3 * pressure)
    ink = tint or ((60, 65, 59) if pencil else (29, 44, 36))
    color = tuple(round(paper[k] * (1 - opacity) + ink[k] * opacity) for k in range(3))
    radius = unit * ((.5 + .95 * pressure) if pencil else (.7 + 1.5 * pressure)) / 2
    a, b = np.array(a), np.array(b)
    delta = b - a
    length = float(np.linalg.norm(delta))
    if length < 1e-6:
        return
    normal = np.array([-delta[1], delta[0]]) * radius / length
    polygon = np.rint(np.array([a + normal, b + normal, b - normal, a - normal]) * 256).astype(np.int32)
    cv2.fillConvexPoly(canvas, polygon, color, cv2.LINE_AA, shift=8)
    for p in (a, b):
        cv2.circle(canvas, tuple(np.rint(p * 256).astype(int)), max(1, round(radius * 256)), color, -1, cv2.LINE_AA, shift=8)


SHORT_SIDE = {'720p': 720, '1080p': 1080, '4k': 2160}


def even(value):
    return max(2, int(round(value / 2)) * 2)


def dimensions(settings, scene=None):
    """Frame size for the export. "auto" follows the picture's own shape, kept between 9:16 and 16:9."""
    short = SHORT_SIDE.get(settings['resolution'], 720)
    ratio = settings['ratio']
    if ratio == 'auto':
        aspect = scene['width'] / scene['height'] if scene else 16 / 9
        aspect = min(16 / 9, max(9 / 16, aspect))
        return (even(short * aspect), short) if aspect >= 1 else (short, even(short / aspect))
    if ratio == '1:1':
        return short, short
    if ratio == '4:5':
        return short, even(short * 5 / 4)
    if ratio == '9:16':
        return short, even(short * 16 / 9)
    return even(short * 16 / 9), short


def frame_point(path, amount):
    """Position along the paint path at this point of the colour reveal (0..1)."""
    if not path:
        return None
    t = min(len(path) - 1., max(0., amount * len(path) - .5))
    i = int(t)
    j, f = min(len(path) - 1, i + 1), t - int(t)
    return (path[i][0] + (path[j][0] - path[i][0]) * f, path[i][1] + (path[j][1] - path[i][1]) * f)


def render(folder: Path, settings, update, output=None):
    ffmpeg = os.environ.get('FFMPEG_PATH') or shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('FFmpeg is missing. Install FFmpeg and restart the server.')
    scene = load_scene(folder)
    from .steps import StepFrames
    step_frames = StepFrames(folder, scene) if scene.get('mode') == 'steps' else None
    width, height = dimensions(settings, scene)
    scale = min(width * .9 / scene['width'], height * .9 / scene['height'])
    ox = round((width - scene['width'] * scale) / 2)
    oy = round((height - scene['height'] * scale) / 2)
    events = scene['timeline']
    def screen(point):
        return (point[0] * scale + ox, point[1] * scale + oy)
    unit = min(width, height) / 540
    mark_unit = unit * pen_weight(scene.get('line_width'), unit / scale)  # drawn line weight follows the artwork's outlines
    rgb = np.array(Image.open(folder / 'source.png').convert('RGB'))
    size = (round(scene['width'] * scale), round(scene['height'] * scale))
    source = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)
    reveal = cv2.resize(np.array(Image.open(folder / 'reveal.png')), size)
    board = BOARDS.get(settings.get('canvas'))
    ground = board or PAPER
    keep_chalk = None
    if board:  # on a chalkboard the picture's paper-coloured background becomes the board, so colour lands on it cleanly
        closeness = np.clip(1 - np.abs(source.astype(np.int16) - np.array(PAPER)).sum(axis=2) / 24, 0, 1)[..., None]
        # ...and its black outlines are never painted over the chalk lines, which stay the drawing's outline
        gray = cv2.cvtColor(source, cv2.COLOR_RGB2GRAY)
        keep_chalk = 1 - cv2.GaussianBlur(np.float32(ink_mask(source, gray)), (5, 5), 0)[..., None]
        source = np.uint8(source * (1 - closeness) + np.array(board) * closeness)
    paper = np.full((height, width, 3), ground, np.uint8)
    tint = hex_to_rgb(settings['ink_color']) if settings.get('ink_color') else None  # the brand kit's drawing colour
    if board and not tint:
        tint = CHALK
    ink = tint or ((60, 65, 59) if settings['style'] == 'pencil' else (29, 44, 36))
    tone = settings.get('hand') if settings.get('hand') in hands.TONES else None  # a realistic hand, or the plain pencil
    paint = scene.get('paint_path') or []
    final = Path(output) if output else folder / 'output.mp4'
    temporary = final.with_suffix('.partial.mp4')
    fps = 24
    frames = settings['duration'] * fps
    command = [ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
               '-s', f'{width}x{height}', '-r', str(fps), '-i', '-', '-an', '-c:v', 'libx264',
               '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(temporary)]
    log_path = final.with_suffix('.log')
    index = 0
    with log_path.open('wb') as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
        try:
            for frame in range(frames):
                progress = frame / max(1, frames - 1)
                line_end, reveal_span = phase_bounds(settings['duration'], settings['color'])
                draw_progress = min(1, progress / line_end)
                while index < len(events) and events[index]['end'] <= draw_progress:
                    event = events[index]
                    if event['kind'] == 'draw':
                        draw_mark(paper, screen(event['a']), screen(event['b']), event['pressure'], settings['style'], mark_unit, tint, ground)
                    index += 1
                canvas = paper.copy()
                tip, lift = None, 0
                if index < len(events):
                    event = events[index]
                    fraction = (draw_progress - event['start']) / (event['end'] - event['start'])
                    position, lift = event_position(event, fraction)
                    tip = screen(position)
                    if event['kind'] == 'draw':
                        draw_mark(canvas, screen(event['a']), tip, event['pressure'], settings['style'], mark_unit, tint, ground)
                if settings['color'] and progress > line_end:
                    amount = min(1, (progress - line_end) / reveal_span)
                    mask = np.clip((amount * 270 - reveal.astype(np.float32)) / 20, 0, 1)[..., None]
                    if keep_chalk is not None:
                        mask = mask * keep_chalk
                    area = canvas[oy:oy + size[1], ox:ox + size[0]]
                    area[:] = np.uint8(area * (1 - mask) + source * mask)
                stage_label = 'Drawing outlines' if progress < line_end else 'Revealing color'
                if step_frames:
                    stage_image, stage_tip, lift, stage_label = step_frames.frame(progress)
                    canvas = np.full((height, width, 3), ground, np.uint8)
                    canvas[oy:oy+size[1], ox:ox+size[0]] = cv2.resize(stage_image, size, interpolation=cv2.INTER_AREA)
                    tip = screen(stage_tip) if stage_tip is not None else None
                painting = settings['color'] and not step_frames and line_end < progress < line_end + reveal_span
                if settings['pen'] and tone and painting and paint:
                    spot = frame_point(paint, (progress - line_end) / reveal_span)
                    hands.draw(canvas, tone, 'brush', screen(spot))
                elif settings['pen'] and tone and tip and (step_frames or progress < line_end):
                    hands.draw(canvas, tone, 'pen' if settings['style'] == 'ink' else 'pencil', tip, lift)
                elif settings['pen'] and tip and (step_frames or progress < line_end):
                    x, y = tip
                    if lift > 0:
                        cv2.ellipse(canvas, (round(x + 8 * unit), round(y + 3 * unit)),
                                    (max(1, round(7 * unit)), max(1, round(2 * unit))), 0, 0, 360,
                                    (221, 223, 214), -1, cv2.LINE_AA)
                    y -= lift * 10 * unit
                    x += lift * 3 * unit
                    # A graphic pencil with its point exactly on the active stroke.
                    pts = np.array([[x, y], [x + 17*unit, y - 46*unit], [x + 28*unit, y - 40*unit], [x + 5*unit, y + 2*unit]], np.int32)
                    cv2.fillConvexPoly(canvas, pts, (207, 162, 87), cv2.LINE_AA)
                    cv2.circle(canvas, (round(x), round(y)), max(2, round(unit * 2)), ink, -1, cv2.LINE_AA)
                if settings.get('watermark'):
                    watermark.apply(canvas)
                elif settings.get('logo'):
                    watermark.apply_logo(canvas, settings['logo'], settings.get('logo_corner', 'bottom-right'))
                process.stdin.write(canvas.tobytes())
                if frame % 12 == 0:
                    update(round(5 + progress * (86 if settings.get('end_card') else 91)), stage_label)
            if settings.get('end_card'):
                update(92, 'Adding the end card')
                for card in endcard.frames(canvas, fps, ground):
                    process.stdin.write(card.tobytes())
            update(96, 'Finishing your video')
            process.stdin.close()
            if process.wait(timeout=60) != 0:
                raise RuntimeError('FFmpeg could not encode the video. Check the render log.')
            temporary.replace(final)
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            temporary.unlink(missing_ok=True)
            raise
    update(100, 'Ready to download')
    return final
