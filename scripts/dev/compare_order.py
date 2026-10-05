"""Show how the drawing order builds up, old against new, for one or more pictures.

    .venv/bin/python scripts/dev/compare_order.py out.png picture.jpg [more.jpg ...]

Each picture gets two rows (old: coarse to fine over the whole picture; new: part by part, with pairs, then texture) and five
columns showing the strokes drawn after 10, 25, 50, 75 and 100% of the way. Strokes are coloured from blue (first) to red (last).
"""
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.artistry import order_strokes, order_strokes_human  # noqa: E402
from backend.pipeline import load_scene, prepare_image  # noqa: E402

CELL = 300
STEPS = (.10, .25, .50, .75, 1.0)


def panel(paths, size, upto):
    scale = (CELL - 8) / max(size)
    canvas = np.full((CELL, CELL, 3), 255, np.uint8)
    for k, path in enumerate(paths[:upto]):
        color = cv2.applyColorMap(np.array([[int(255 * k / max(1, len(paths) - 1))]], np.uint8), cv2.COLORMAP_TURBO)[0, 0].tolist()
        points = (np.asarray(path, float) * scale + 4).astype(np.int32)
        cv2.polylines(canvas, [points], False, color, 2, cv2.LINE_AA)
    return Image.fromarray(canvas[:, :, ::-1])


def main():
    out, pictures = Path(sys.argv[1]), sys.argv[2:]
    rows = []
    for picture in pictures:
        with tempfile.TemporaryDirectory() as work:
            folder = Path(work)
            prepare_image(Path(picture), folder)
            scene = load_scene(folder)
        paths = [np.asarray(p, float) for p in scene['paths']]
        size = (scene['width'], scene['height'])
        for label, order in (('old', order_strokes), ('new', order_strokes_human)):
            ordered = order(paths, *size)
            row = Image.new('RGB', (CELL * len(STEPS), CELL + 16), 'white')
            ImageDraw.Draw(row).text((4, 2), f'{Path(picture).name}: {label} ({len(ordered)} strokes)', fill=(0, 0, 0))
            for column, share in enumerate(STEPS):
                row.paste(panel(ordered, size, max(1, round(len(ordered) * share))), (column * CELL, 16))
            rows.append(row)
    sheet = Image.new('RGB', (rows[0].width, sum(r.height for r in rows)), 'white')
    y = 0
    for row in rows:
        sheet.paste(row, (0, y))
        y += row.height
    sheet.save(out)
    print(out)


main()
