"""The realistic drawing hand: a cut-out photo of a hand holding an ink pen or a pencil (line phase, for the Ink and
Pencil styles) or a brush (colour phase), in three
skin tones. The artwork lives in frontend/public/hands/ (made by scripts/hands/cutout.py) so the browser preview and the
MP4 renderer use the very same images; hands.json records where the tip is, and that point is put on the active line.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

import cv2
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


MAX_TURN = 28        # degrees the hand may turn from its photographed pose
PIVOT = (.74, 1.45)  # where the arm comes from, as a share of the frame (below the picture, a little right of centre)
FLIP_LEFT, FLIP_BACK = .36, .50  # the brush is held by the left hand while it works on the left of the picture (with hysteresis)


@lru_cache(maxsize=12)
def arm_direction(key, height, flip=False):
    """Unit vector from the pen tip towards the forearm in the photograph (the far end of the artwork)."""
    _, alpha, tip = scaled(key, height)
    if flip:
        alpha, tip = alpha[:, ::-1], (alpha.shape[1] - tip[0], tip[1])
    ys, xs = np.nonzero(alpha[..., 0] > .5)
    distance = np.hypot(xs - tip[0], ys - tip[1])
    far = distance >= np.quantile(distance, .75)
    vector = np.array([xs[far].mean() - tip[0], ys[far].mean() - tip[1]])
    return vector / max(1e-6, float(np.hypot(*vector)))


@lru_cache(maxsize=320)
def turned(key, height, angle, flip=False):
    """The hand turned `angle` degrees (clockwise on screen) about its tip: (premultiplied rgb, alpha, tip)."""
    rgb, alpha, tip = scaled(key, height)
    if flip:  # the mirror image: a left hand
        rgb, alpha, tip = rgb[:, ::-1], alpha[:, ::-1], (alpha.shape[1] - tip[0], tip[1])
    h, w = alpha.shape[:2]
    matrix = cv2.getRotationMatrix2D((float(tip[0]), float(tip[1])), -float(angle), 1.0)
    corners = cv2.transform(np.array([[[0, 0], [w, 0], [w, h], [0, h]]], np.float32), matrix)[0]
    low, high = corners.min(axis=0), corners.max(axis=0)
    matrix[:, 2] -= low
    size = (int(math.ceil(high[0] - low[0])), int(math.ceil(high[1] - low[1])))
    packed = np.dstack([rgb * alpha, alpha]).astype(np.float32)
    out = cv2.warpAffine(packed, matrix, size, flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    return out[..., :3], out[..., 3:], (float(tip[0] - low[0]), float(tip[1] - low[1]))


def natural_angle(key, height, point, frame, flip=False):
    """How far to turn the hand so its forearm points from the tip towards where the arm comes from (below the picture)."""
    arm = arm_direction(key, height, flip)
    pivot_x = (1 - PIVOT[0]) if flip else PIVOT[0]
    target = np.array([pivot_x * frame[0] - point[0], PIVOT[1] * frame[1] - point[1]])
    delta = math.degrees(math.atan2(target[1], target[0]) - math.atan2(arm[1], arm[0]))
    delta = (delta + 180) % 360 - 180
    return int(round(max(-MAX_TURN, min(MAX_TURN, delta)) / 2) * 2)


def draw(canvas, tone, tool, point, lift=0., natural=False, pose=None):
    """Composite the hand onto an RGB frame so its tip sits on `point`. Returns False when no artwork is available."""
    key = artwork(tone, tool)
    if key is None:
        return False
    frame_h, frame_w = canvas.shape[:2]
    # The image includes a long forearm; size it so the hand itself is SIZE of the frame.
    height = max(40, round(min(frame_w, frame_h) * SIZE / manifest()[key].get('hand', 1)))
    if natural:  # turn the hand about the tip so the arm comes from below instead of stretching across the picture
        flip = bool(pose.get('flip')) if pose is not None else False
        if pose is not None:                       # switch hands with some hysteresis so it never flickers
            share = point[0] / frame_w
            flip = True if share < FLIP_LEFT else (False if share > FLIP_BACK else flip)
            pose['flip'] = flip
        rgb, alpha, tip = turned(key, height, natural_angle(key, height, point, (frame_w, frame_h), flip), flip)
    else:
        rgb, alpha, tip = scaled(key, height)
        rgb = rgb * alpha
    unit = min(frame_w, frame_h) / 540
    x = round(point[0] - tip[0] + lift * 3 * unit)
    y = round(point[1] - tip[1] - lift * 12 * unit)  # between strokes the hand lifts off the page a little
    h, w = alpha.shape[:2]
    left, top, right, bottom = max(0, x), max(0, y), min(frame_w, x + w), min(frame_h, y + h)
    if left >= right or top >= bottom:
        return True
    area = canvas[top:bottom, left:right]
    a = alpha[top - y:bottom - y, left - x:right - x]
    area[:] = np.uint8(area * (1 - a) + rgb[top - y:bottom - y, left - x:right - x])
    return True
