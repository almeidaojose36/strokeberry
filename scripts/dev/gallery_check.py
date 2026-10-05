"""Run the experimental drawing order and painting over every gallery picture and report where it struggles.

    .venv/bin/python scripts/dev/gallery_check.py out_prefix [names ...]

Writes <out_prefix>-1.png, -2.png... (nine pictures per sheet: the source, the lines after a third and two thirds of the
drawing, and the colour order from blue = first to red = last) and prints one row per picture: strokes (current -> new), pen
lifts, how far the brush is from the colour it paints (median share of the picture's diagonal), and the time it took.
"""
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.artistry import make_timeline, order_strokes_human, silhouette_mask  # noqa: E402
from backend.inkfill import ink_masks, inside_share, outline_strokes  # noqa: E402
from backend.paintorder import region_ranks  # noqa: E402
from backend.pipeline import BRUSH_DEPTH, PAPER, brush_texture, frame_point, paint_path, prepare_image  # noqa: E402

CELL = 240


def experimental(scene, rgb):
    """The new order, timeline, colour ranks and brush path for a prepared picture."""
    distance = np.abs(rgb.astype(np.float32) - np.array(PAPER, np.float32)).sum(axis=2)
    _, thick = ink_masks(rgb, distance, scene.get('line_width'))
    outlines = outline_strokes(thick)
    solid = cv2.dilate(thick.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    kept = [np.asarray(p, float) for p in scene['paths'] if inside_share(p, solid) < .7]
    human = [p.tolist() for p in order_strokes_human(kept + outlines, scene['width'], scene['height'], (), silhouette_mask(distance >= 14))]
    ranks = region_ranks(rgb, distance, brush_texture(distance.shape), BRUSH_DEPTH, scene.get('line_width'))
    u8 = np.uint8(ranks * 245)
    path = paint_path(u8, distance > 30, samples=360, tolerance=2, reach_share=.025, offset=3)
    return human, make_timeline(human, human_pace=True), ranks, u8, path, distance


def brush_gap(u8, path, distance):
    diag = float(np.hypot(*u8.shape))
    visible, level, gaps = distance > 30, u8.astype(np.float32), []
    for f in range(1, 140):
        a = f / 150
        ys, xs = np.nonzero(visible & (level <= a * 270 - 3) & (level > (a - 1 / 150) * 270 - 3))
        if len(xs) >= 30 and path:
            spot = frame_point(path, a)
            gaps.append(np.hypot(xs.mean() - spot[0], ys.mean() - spot[1]) / diag)
    return float(np.median(gaps)) if gaps else float('nan')


def panel(paths, size, share):
    scale = (CELL - 6) / max(size)
    canvas = np.full((CELL, CELL, 3), 255, np.uint8)
    count = max(1, round(len(paths) * share))
    for k, path in enumerate(paths[:count]):
        color = cv2.applyColorMap(np.array([[int(255 * k / max(1, len(paths) - 1))]], np.uint8), cv2.COLORMAP_TURBO)[0, 0].tolist()
        cv2.polylines(canvas, [(np.asarray(path, float) * scale + 3).astype(np.int32)], False, color, 2, cv2.LINE_AA)
    return canvas


def main():
    prefix, wanted = sys.argv[1], sys.argv[2:]
    files = sorted((ROOT / 'assets' / 'gallery-src').glob('*.jpg'))
    rows, report = [], []
    for f in files:
        if wanted and f.stem not in wanted:
            continue
        started = time.time()
        with tempfile.TemporaryDirectory() as work:
            scene = prepare_image(f, Path(work))
            rgb = np.array(Image.open(Path(work) / 'source.png').convert('RGB'))
        human, timeline, ranks, u8, path, distance = experimental(scene, rgb)
        size = (scene['width'], scene['height'])
        lifts_old = sum(1 for e in scene['timeline'] if e['kind'] == 'lift')
        lifts_new = sum(1 for e in timeline if e['kind'] == 'lift')
        lengths = np.array([np.sum(np.hypot(*np.diff(np.asarray(p), axis=0).T)) for p in human]) / np.hypot(*size)
        gap = brush_gap(u8, path, distance)
        report.append((f.stem, scene['line_method'], scene['strokes'], len(human), lifts_old, lifts_new, float((lengths < .03).mean()), gap, time.time() - started))
        vis = cv2.applyColorMap(np.uint8(ranks * 255), cv2.COLORMAP_TURBO)
        vis[distance < 14] = 255
        row = [cv2.resize(rgb[:, :, ::-1], (CELL, CELL)), panel(human, size, 1 / 3), panel(human, size, 2 / 3), cv2.resize(vis, (CELL, CELL))]
        label = np.full((16, CELL * 4, 3), 255, np.uint8)
        cv2.putText(label, f.stem, (4, 12), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 0), 1, cv2.LINE_AA)
        rows.append(np.vstack([label, np.hstack(row)]))
    print(f"{'picture':<12}{'method':<9}{'strokes':>12}{'pen lifts':>14}{'tiny':>7}{'brush gap':>11}{'secs':>6}")
    for name, method, a, b, la, lb, tiny, gap, secs in report:
        print(f'{name:<12}{method:<9}{f"{a}->{b}":>12}{f"{la}->{lb}":>14}{tiny * 100:>6.0f}%{gap * 100:>10.1f}%{secs:>6.1f}')
    for n in range(0, len(rows), 9):
        Image.fromarray(np.vstack(rows[n:n + 9])[:, :, ::-1]).save(f'{prefix}-{n // 9 + 1}.png')


main()
