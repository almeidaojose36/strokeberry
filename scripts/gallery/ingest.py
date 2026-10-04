"""Build the in-app example library from source images.

    .venv/bin/python scripts/gallery/ingest.py

Reads images named by their ID from marketing/gallery-prompts.md (e.g. animals-01-fox.png) in any of the
SOURCES folders, plus the starter seeds in assets/gallery-src/, and writes web-sized images, thumbnails and
library.json to frontend/public/library/. Names like "animals-01-fox.png_20260928092703.jpg" (as some image
tools export them) are understood too. Re-run it whenever you add or remove images.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
SOURCES = [ROOT / 'marketing' / 'gallery-source', ROOT / 'marketing' / 'marketing_gallery-source_']
OUT = ROOT / 'frontend' / 'public' / 'library'
CATEGORIES = [('animals', 'Animals'), ('food', 'Food & drink'), ('home', 'Home & interiors'), ('nature', 'Nature'), ('sports', 'Sports'), ('occasion', 'Occasions'),
              ('objects', 'Objects'), ('travel', 'Travel'), ('logo', 'Logos'), ('tutorial', 'Step-by-step')]
# Starter images that already ship with the repo (the strawberry stays out: it's the brand's own art).
SEEDS = {'animals-00-cat': ('assets/gallery-src/cat.jpg', 'Cat'),
         'food-00-coffee': ('assets/gallery-src/coffee.jpg', 'Coffee & croissant'),
         'occasion-00-wreath': ('assets/gallery-src/wreath.jpg', 'Wreath'),
         'objects-00-sneaker': ('assets/gallery-src/sneaker.jpg', 'Sneaker'),
         'tutorial-00-owl': ('assets/gallery-src/owl.jpg', 'Owl steps'),
         # Home & interiors (made with scripts/gallery/generate-hero-art.mjs --set interiors --model z-image)
         'home-01-living-room': ('assets/interiors-src/livingroom-2.jpg', 'Living room'),
         'home-02-armchair': ('assets/interiors-src/armchair-2.jpg', 'Lounge armchair'),
         'home-03-kitchen': ('assets/interiors-src/kitchen-1.jpg', 'Kitchen'),
         'home-04-floor-plan': ('assets/interiors-src/floorplan-2.jpg', 'Floor plan'),
         # Sports: invented athletes in plain flag-coloured kits (generate-hero-art.mjs --set sports --model z-image)
         'sports-01-striker': ('assets/gallery-src/striker.jpg', 'Striker'),
         'sports-02-goalkeeper': ('assets/gallery-src/keeper.jpg', 'Goalkeeper'),
         'sports-03-sprinter': ('assets/gallery-src/sprinter.jpg', 'Sprinter'),
         'sports-04-boxer': ('assets/gallery-src/boxer.jpg', 'Boxer'),
         'sports-05-dunk': ('assets/gallery-src/dunk.jpg', 'Basketball dunk'),
         'sports-06-rugby': ('assets/gallery-src/rugby.jpg', 'Rugby'),
         'sports-07-cricketer': ('assets/gallery-src/cricketer.jpg', 'Cricket'),
         'sports-08-fan': ('assets/gallery-src/fan.jpg', 'Fan with flag')}
# The ID at the start of the file name; anything after it (".png_<timestamp>", etc.) is ignored.
ID = re.compile(r'^([a-z]+)-(\d\d)-([a-z0-9]+(?:-[a-z0-9]+)*)')
TITLES = {'icecream': 'Ice cream', 'avocado': 'Avocado toast', 'boba': 'Bubble tea', 'plant-books': 'Books & plant',
          'bakery': 'Sunny Loaf Bakery', 'plants': 'Leafy Corner', 'barber': 'Sharp & Co.', 'fitness': 'Pulse Fit',
          'petshop': 'Happy Paws', 'van': 'Camper van', 'wedding': 'Wedding rings', 'heart': 'Heart balloon',
          'graduation': 'Graduation cap'}
EDGE_MARGIN = .06  # empty border added around art that touches the edge, so nothing looks cut off


def title_from(category, slug):
    title = TITLES.get(slug, slug.replace('-', ' ').capitalize())
    return f'{title} steps' if category == 'tutorial' else title


def pad_if_touching(image):
    """Give art that runs into the image edge a white margin. Tutorial grids are left alone."""
    ink = np.asarray(image).min(axis=2) < 235
    rows, cols = np.where(ink.any(axis=1))[0], np.where(ink.any(axis=0))[0]
    if not len(rows):
        return image
    edge = round(min(image.size) * .02)
    height, width = ink.shape
    if rows[0] > edge and cols[0] > edge and rows[-1] < height - 1 - edge and cols[-1] < width - 1 - edge:
        return image
    side = round(max(image.size) * (1 + 2 * EDGE_MARGIN))
    padded = Image.new('RGB', (side, side), 'white')
    padded.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    return padded


def main():
    sources = {key: (ROOT / path, title) for key, (path, title) in SEEDS.items()}
    skipped = []
    for path in sorted(p for folder in SOURCES if folder.exists() for p in folder.glob('*')):
        if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
            continue
        match = ID.match(path.name.lower())
        if not match or match.group(1) not in dict(CATEGORIES):
            skipped.append(path.name)
            continue
        item_id = match.group(0)
        sources[item_id] = (path, title_from(match.group(1), match.group(3)))
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob('*'):
        if old.name != 'library.json':
            old.unlink()
    items = []
    for item_id, (path, title) in sorted(sources.items()):
        category = item_id.split('-')[0]
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert('RGBA')
            flat = Image.new('RGB', image.size, 'white')
            flat.paste(image, mask=image.getchannel('A'))
            if category != 'tutorial':
                flat = pad_if_touching(flat)
            flat.thumbnail((1400, 1400), Image.LANCZOS)
            flat.save(OUT / f'{item_id}.jpg', quality=90, optimize=True)
            thumb = flat.copy()
            thumb.thumbnail((360, 360), Image.LANCZOS)
            thumb.save(OUT / f'{item_id}-thumb.webp', quality=82)
        items.append({'id': item_id, 'title': title, 'category': category, 'image': f'{item_id}.jpg',
                      'thumb': f'{item_id}-thumb.webp', 'tutorial': category == 'tutorial'})
    used = {item['category'] for item in items}
    manifest = {'categories': [{'id': c, 'name': n} for c, n in CATEGORIES if c in used], 'items': items}
    (OUT / 'library.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'{len(items)} examples written to {OUT.relative_to(ROOT)}')
    if skipped:
        print('Skipped (name must start with an ID like animals-01-fox):', ', '.join(skipped), file=sys.stderr)


if __name__ == '__main__':
    main()
