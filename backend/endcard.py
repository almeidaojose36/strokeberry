"""The closing card on Free exports: the approved mascot (scaled only, never redrawn), "Made with Strokeberry" and the
address. Pro and video-pack exports end on the finished drawing instead."""
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent / 'assets'
SECONDS = 2.5
FADE = .4  # seconds of cross-fade from the finished drawing
INK, MUTED, BERRY = (27, 27, 27), (95, 92, 88), (200, 30, 42)


def _font(size, weight):
    try:
        font = ImageFont.truetype(str(ASSETS / 'Figtree.ttf'), size)
        try:
            font.set_variation_by_axes([weight])
        except (OSError, AttributeError):
            pass
        return font
    except OSError:
        return ImageFont.load_default()


@lru_cache(maxsize=8)
def card(width, height, background):
    """The finished card as an RGB array for this frame size and background colour."""
    image = Image.new('RGB', (width, height), background)
    dark = sum(background) < 300  # chalkboards get light text
    unit = min(width, height)
    mascot = Image.open(ASSETS / 'endcard-mascot.png').convert('RGBA')
    mascot_h = round(unit * .42)
    mascot = mascot.resize((round(mascot.width * mascot_h / mascot.height), mascot_h), Image.LANCZOS)
    title_font, url_font = _font(round(unit * .07), 750), _font(round(unit * .042), 600)
    title, url = 'Made with Strokeberry', 'strokeberry.com'
    draw = ImageDraw.Draw(image)
    title_box, url_box = draw.textbbox((0, 0), title, font=title_font), draw.textbbox((0, 0), url, font=url_font)
    gap = round(unit * .04)
    total = mascot_h + gap + (title_box[3] - title_box[1]) + gap // 2 + (url_box[3] - url_box[1])
    top = (height - total) // 2
    image.paste(mascot, ((width - mascot.width) // 2, top), mascot)
    y = top + mascot_h + gap
    draw.text(((width - (title_box[2] - title_box[0])) // 2 - title_box[0], y - title_box[1]), title, font=title_font,
              fill=(245, 243, 236) if dark else INK)
    y += title_box[3] - title_box[1] + gap // 2
    draw.text(((width - (url_box[2] - url_box[0])) // 2 - url_box[0], y - url_box[1]), url, font=url_font,
              fill=(236, 120, 126) if dark else BERRY)
    return np.asarray(image)


def frames(last_frame, fps, background):
    """Yield the end-card frames, starting with a cross-fade from the last frame of the drawing."""
    height, width = last_frame.shape[:2]
    target = card(width, height, tuple(int(c) for c in background)).astype(np.float32)
    start = last_frame.astype(np.float32)
    for i in range(round(SECONDS * fps)):
        t = min(1., (i + 1) / (FADE * fps))
        yield np.uint8(start * (1 - t) + target * t)
