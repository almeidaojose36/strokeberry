"""Build the pictures used by the studio's "How it works" guide.

    .venv/bin/python scripts/gallery/guide_images.py

Crops real studio screenshots from the logo tutorial's capture (videos/strokeberry-tutorial-logo/capture/app,
made by scripts/tutorials/capture-studio.mjs) and gallery images from frontend/public/library/, and writes
WebP images to frontend/public/guide/.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / 'videos' / 'strokeberry-tutorial-logo' / 'capture' / 'app'
LIBRARY = ROOT / 'frontend' / 'public' / 'library'
OUT = ROOT / 'frontend' / 'public' / 'guide'
PANEL = (255, 253, 248)
SIZE = (640, 480)  # every step picture is 4:3


def save(image, name, size=SIZE):
    image = image.convert('RGB')
    image.thumbnail(size, Image.LANCZOS)
    canvas = Image.new('RGB', size, PANEL)
    canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    canvas.save(OUT / f'{name}.webp', quality=86)


def rounded(image, radius):
    mask = Image.new('L', image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius, fill=255)
    tile = Image.new('RGBA', image.size)
    tile.paste(image, mask=mask)
    return tile


def examples_collage():
    """Step 1: a 2×2 grid of gallery examples."""
    ids = ['animals-01-fox', 'logo-01-bakery', 'food-01-cupcake', 'travel-02-hot-air-balloon']
    canvas = Image.new('RGBA', (1280, 960), PANEL + (255,))
    draw = ImageDraw.Draw(canvas)
    tile, gap = 400, 40
    left, top = (1280 - 2 * tile - gap) // 2, (960 - 2 * tile - gap) // 2
    for i, item in enumerate(ids):
        x, y = left + (i % 2) * (tile + gap), top + (i // 2) * (tile + gap)
        draw.rounded_rectangle((x - 3, y - 3, x + tile + 2, y + tile + 2), 34, fill=(226, 209, 178))
        image = Image.open(LIBRARY / f'{item}.jpg').convert('RGB').resize((tile, tile), Image.LANCZOS)
        canvas.alpha_composite(rounded(image, 32), (x, y))
    save(canvas, 'step-1-image')


def screenshot(name, box):
    return Image.open(CAPTURE / f'{name}.png').convert('RGB').crop(box)


def export_ready():
    """Step 4: "Your video is ready" heading above the Download button (the video frame is left out)."""
    heading = screenshot('12-ready', (80, 360, 1090, 780))
    ImageDraw.Draw(heading).rectangle((780, 0, heading.width, 160), fill=PANEL)  # the dialog's close button
    button = screenshot('12-ready', (80, 1990, 1090, 2165))
    canvas = Image.new('RGB', (1010, 760), PANEL)
    canvas.paste(heading, (0, 60))
    canvas.paste(button, (0, 60 + heading.height + 90))
    save(canvas, 'step-4-export')


def tips():
    """"What works best": the fox on plain white vs. the same fox lost in a busy, cluttered background (16:10)."""
    size, fox_height = (640, 400), 360
    fox = Image.open(LIBRARY / 'animals-01-fox.jpg').convert('RGB')
    fox = fox.crop(ImageOps.invert(fox).getbbox()).resize((round(fox.width * fox_height / fox.height), fox_height),
                                                            Image.LANCZOS)
    fox = ImageOps.expand(fox, 12, fill='white')
    at = ((size[0] - fox.width) // 2, (size[1] - fox.height) // 2)
    good = Image.new('RGB', size, 'white')
    good.paste(fox, at)
    good.save(OUT / 'tip-good.webp', quality=86)
    busy = Image.new('RGB', size, (236, 214, 160))
    for i, item in enumerate(['nature-04-monstera', 'food-02-pizza', 'nature-05-tree', 'objects-06-plant-books',
                              'food-04-burger', 'nature-01-sunflower', 'occasion-03-christmas-tree', 'food-06-boba',
                              'nature-02-cactus', 'food-07-donut']):
        piece = Image.open(LIBRARY / f'{item}.jpg').convert('RGB').resize((260, 260), Image.LANCZOS)
        busy.paste(piece.rotate(i * 37, fillcolor=(236, 214, 160)), ((i % 5) * 140 - 60, (i // 5) * 190 - 50))
    busy = busy.filter(ImageFilter.GaussianBlur(1.5))
    subject = np.asarray(fox).min(axis=2) < 225
    busy.paste(fox, at, Image.fromarray(np.uint8(subject) * 255).filter(ImageFilter.MaxFilter(9)))
    busy.save(OUT / 'tip-busy.webp', quality=86)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    examples_collage()
    save(screenshot('05-style', (78, 400, 1092, 1160)), 'step-2-style')
    save(screenshot('09-preview-2', (47, 215, 1123, 1022)), 'step-3-preview')
    export_ready()
    tips()
    print('guide images written to', OUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
