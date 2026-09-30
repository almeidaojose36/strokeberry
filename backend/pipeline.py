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
        image = Image.fromarray(blend_white_background(np.array(image)))  # the original.png above stays untouched
        image.thumbnail((900, 900))
        image.save(folder / 'source.png')
    rgb = np.array(image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 45, 125)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=lambda c: cv2.arcLength(c, False), reverse=True)
    paths = clean_paths(contours, gray.shape)
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
    for i, label in enumerate(used):
        region = labels == label
        ranks[region] = (i + sweep[region] * .85) / len(used)
    Image.fromarray(np.uint8(ranks * 245)).save(folder / 'reveal.png')
    scene = {'width': image.width, 'height': image.height, 'paths': ordered,
             'version': SCENE_VERSION, 'timeline': make_timeline(ordered),
             'strokes': len(ordered), 'palette': [palette[k].tolist() for k in used]}
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


def draw_mark(canvas, a, b, pressure, style, unit, tint=None):
    """Subpixel strokes preserve pressure changes at every export resolution."""
    pencil = style == 'pencil'
    opacity = (.35 + .45 * pressure) if pencil else (.65 + .3 * pressure)
    ink = tint or ((60, 65, 59) if pencil else (29, 44, 36))
    color = tuple(round(PAPER[k] * (1 - opacity) + ink[k] * opacity) for k in range(3))
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


def dimensions(settings):
    long = 1920 if settings['resolution'] == '1080p' else 1280
    if settings['ratio'] == '1:1':
        return (1080, 1080) if long == 1920 else (720, 720)
    short = 1080 if long == 1920 else 720
    return (short, long) if settings['ratio'] == '9:16' else (long, short)


def render(folder: Path, settings, update, output=None):
    ffmpeg = os.environ.get('FFMPEG_PATH') or shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('FFmpeg is missing. Install FFmpeg and restart the server.')
    scene = load_scene(folder)
    from .steps import StepFrames
    step_frames = StepFrames(folder, scene) if scene.get('mode') == 'steps' else None
    width, height = dimensions(settings)
    scale = min(width * .9 / scene['width'], height * .9 / scene['height'])
    ox = round((width - scene['width'] * scale) / 2)
    oy = round((height - scene['height'] * scale) / 2)
    events = scene['timeline']
    def screen(point):
        return (point[0] * scale + ox, point[1] * scale + oy)
    unit = min(width, height) / 540
    rgb = np.array(Image.open(folder / 'source.png').convert('RGB'))
    size = (round(scene['width'] * scale), round(scene['height'] * scale))
    source = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)
    reveal = cv2.resize(np.array(Image.open(folder / 'reveal.png')), size)
    paper = np.full((height, width, 3), PAPER, np.uint8)
    tint = hex_to_rgb(settings['ink_color']) if settings.get('ink_color') else None  # the brand kit's drawing colour
    ink = tint or ((60, 65, 59) if settings['style'] == 'pencil' else (29, 44, 36))
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
                        draw_mark(paper, screen(event['a']), screen(event['b']), event['pressure'], settings['style'], unit, tint)
                    index += 1
                canvas = paper.copy()
                tip, lift = None, 0
                if index < len(events):
                    event = events[index]
                    fraction = (draw_progress - event['start']) / (event['end'] - event['start'])
                    position, lift = event_position(event, fraction)
                    tip = screen(position)
                    if event['kind'] == 'draw':
                        draw_mark(canvas, screen(event['a']), tip, event['pressure'], settings['style'], unit, tint)
                if settings['color'] and progress > line_end:
                    amount = min(1, (progress - line_end) / reveal_span)
                    mask = np.clip((amount * 270 - reveal.astype(np.float32)) / 20, 0, 1)[..., None]
                    area = canvas[oy:oy + size[1], ox:ox + size[0]]
                    area[:] = np.uint8(area * (1 - mask) + source * mask)
                stage_label = 'Drawing outlines' if progress < line_end else 'Revealing color'
                if step_frames:
                    stage_image, stage_tip, lift, stage_label = step_frames.frame(progress)
                    canvas = np.full((height, width, 3), PAPER, np.uint8)
                    canvas[oy:oy+size[1], ox:ox+size[0]] = cv2.resize(stage_image, size, interpolation=cv2.INTER_AREA)
                    tip = screen(stage_tip) if stage_tip is not None else None
                if settings['pen'] and tip and (step_frames or progress < line_end):
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
                    update(round(5 + progress * 91), stage_label)
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
