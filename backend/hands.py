"""The realistic drawing hand: a cut-out photo of a hand holding a pencil (line phase) or a brush (colour phase), in three
skin tones. The artwork lives in frontend/public/hands/ (made by scripts/hands/cutout.py) so the browser preview and the
MP4 renderer use the very same images; hands.json records where the tip is, and that point is put on the active line.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

FOLDER = Path(__file__).resolve().parents[1] / 'frontend' / 'public' / 'hands'
TONES = ('light', 'medium', 'dark')
SIZE = .62  # height of the hand (without the forearm) as a share of the frame's shorter side


@lru_cache(maxsize=1)
def manifest():
    try:
        return json.loads((FOLDER / 'hands.json').read_text())
    except (OSError, ValueError):
        return {}


def artwork(tone, tool):
    """The manifest key to use, falling back to the pencil hand when a brush hand of that tone is missing."""
    for key in (f'{tone}-{tool}', f'{tone}-pencil'):
        if key in manifest() and (FOLDER / manifest()[key]['file']).exists():
            return key
    return None


@lru_cache(maxsize=12)
def scaled(key, height):
    """(rgb float32, alpha float32 H×W×1, tip (x, y) in pixels) for this hand drawn `height` pixels tall."""
    entry = manifest()[key]
    image = Image.open(FOLDER / entry['file']).convert('RGBA')
    width = max(1, round(height * image.width / image.height))
    image = image.resize((width, height), Image.LANCZOS)
    array = np.asarray(image).astype(np.float32)
    tip = (entry['tip'][0] * width, entry['tip'][1] * height)
    return array[..., :3], array[..., 3:] / 255.0, tip


def draw(canvas, tone, tool, point, lift=0.):
    """Composite the hand onto an RGB frame so its tip sits on `point`. Returns False when no artwork is available."""
    key = artwork(tone, tool)
    if key is None:
        return False
    frame_h, frame_w = canvas.shape[:2]
    # The image includes a long forearm; size it so the hand itself is SIZE of the frame.
    rgb, alpha, tip = scaled(key, max(40, round(min(frame_w, frame_h) * SIZE / manifest()[key].get('hand', 1))))
    unit = min(frame_w, frame_h) / 540
    x = round(point[0] - tip[0] + lift * 3 * unit)
    y = round(point[1] - tip[1] - lift * 12 * unit)  # between strokes the hand lifts off the page a little
    h, w = alpha.shape[:2]
    left, top, right, bottom = max(0, x), max(0, y), min(frame_w, x + w), min(frame_h, y + h)
    if left >= right or top >= bottom:
        return True
    area = canvas[top:bottom, left:right]
    a = alpha[top - y:bottom - y, left - x:right - x]
    area[:] = np.uint8(area * (1 - a) + rgb[top - y:bottom - y, left - x:right - x] * a)
    return True
