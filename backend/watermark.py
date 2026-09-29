"""The Free-plan watermark: a small white pill with the approved compact mark and "strokeberry.com".
Bottom-right on landscape/square; top-left on 9:16, where TikTok/Reels buttons and captions cover the bottom
and right. Built once per video size, then alpha-blended onto every frame. (Brand rule: at this size — under
~48 px — the compact mark is used, not the full mascot.)"""
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent / 'assets'
INK = (27, 27, 27)


@lru_cache(maxsize=8)
def overlay(width, height):
    """Return (x, y, rgb, alpha) for a width×height frame; alpha is float32 in 0..1."""
    unit = min(width, height)
    pill_h = max(28, round(unit * .075))
    pad = round(pill_h * .18)
    mascot = Image.open(ASSETS / 'watermark-mark.png').convert('RGBA')
    mascot = mascot.crop(mascot.getchannel('A').getbbox())
    mascot_h = pill_h - pad
    mascot = mascot.resize((round(mascot.width * mascot_h / mascot.height), mascot_h), Image.LANCZOS)
    try:
        font = ImageFont.truetype(str(ASSETS / 'Figtree.ttf'), round(pill_h * .42))
        try:
            font.set_variation_by_axes([700])
        except (OSError, AttributeError):
            pass
    except OSError:
        font = ImageFont.load_default()
    text = 'strokeberry.com'
    left, top, right, bottom = font.getbbox(text)
    text_w = right - left
    pill_w = pad + mascot.width + round(pad * .6) + text_w + pad * 2
    image = Image.new('RGBA', (pill_w, pill_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, pill_w - 1, pill_h - 1), radius=pill_h // 2, fill=(255, 255, 255, 225),
                           outline=(27, 27, 27, 40), width=max(1, pill_h // 30))
    image.alpha_composite(mascot, (pad, (pill_h - mascot.height) // 2))
    text_x = pad + mascot.width + round(pad * .6)
    draw.text((text_x - left, (pill_h - (bottom - top)) // 2 - top), text, font=font, fill=INK + (255,))
    margin = round(unit * .03)
    if height > width:  # 9:16 — keep clear of the app buttons (right) and captions (bottom)
        x, y = margin, round(height * .09)
    else:
        x, y = width - pill_w - margin, height - pill_h - margin
    array = np.asarray(image).astype(np.float32)
    return x, y, array[..., :3], array[..., 3:] / 255.0


def apply(canvas):
    """Blend the watermark onto an RGB frame (H×W×3 uint8) in place."""
    height, width = canvas.shape[:2]
    x, y, rgb, alpha = overlay(width, height)
    area = canvas[y:y + rgb.shape[0], x:x + rgb.shape[1]]
    area[:] = np.uint8(area * (1 - alpha) + rgb * alpha)
    return canvas


@lru_cache(maxsize=16)
def _logo_overlay(path, mtime, width, height, corner):
    logo = Image.open(path).convert('RGBA')
    logo = logo.crop(logo.getchannel('A').getbbox() or (0, 0, logo.width, logo.height))
    unit = min(width, height)
    box_h, box_w = round(unit * .13), round(width * .22)
    scale = min(box_h / logo.height, box_w / logo.width)
    logo = logo.resize((max(1, round(logo.width * scale)), max(1, round(logo.height * scale))), Image.LANCZOS)
    margin = round(unit * .03)
    if height > width and corner.startswith('bottom'):  # keep clear of the app buttons on 9:16
        corner = 'top-' + corner.split('-')[1]
    x = margin if corner.endswith('left') else width - logo.width - margin
    y = margin if corner.startswith('top') else height - logo.height - margin
    array = np.asarray(logo).astype(np.float32)
    return x, y, array[..., :3], array[..., 3:] / 255.0


def apply_logo(canvas, path, corner='bottom-right'):
    """Blend a brand logo (Pro) into one corner of an RGB frame (H×W×3 uint8) in place."""
    height, width = canvas.shape[:2]
    x, y, rgb, alpha = _logo_overlay(str(path), Path(path).stat().st_mtime, width, height, corner)
    area = canvas[y:y + rgb.shape[0], x:x + rgb.shape[1]]
    area[:] = np.uint8(area * (1 - alpha) + rgb * alpha)
    return canvas
