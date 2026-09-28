"""Build the in-app example library from source images.

    .venv/bin/python scripts/gallery/ingest.py

Reads marketing/gallery-source/<id>.png|jpg|webp (IDs from marketing/gallery-prompts.md, e.g.
animals-01-fox.png) plus the starter seeds in assets/gallery-src/, and writes web-sized images, thumbnails
and library.json to frontend/public/library/. Re-run it whenever you add or remove images.
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'marketing' / 'gallery-source'
OUT = ROOT / 'frontend' / 'public' / 'library'
CATEGORIES = [('animals', 'Animals'), ('food', 'Food & drink'), ('nature', 'Nature'), ('occasion', 'Occasions'),
              ('objects', 'Objects'), ('travel', 'Travel'), ('logo', 'Logos'), ('tutorial', 'Step-by-step')]
# Starter images that already ship with the repo (the strawberry stays out: it's the brand's own art).
SEEDS = {'animals-00-cat': ('assets/gallery-src/cat.jpg', 'Cat'),
         'food-00-coffee': ('assets/gallery-src/coffee.jpg', 'Coffee & croissant'),
         'occasion-00-wreath': ('assets/gallery-src/wreath.jpg', 'Wreath'),
         'objects-00-sneaker': ('assets/gallery-src/sneaker.jpg', 'Sneaker'),
         'occasion-00-balloon': ('assets/gallery-src/balloon.jpg', 'Balloons'),
         'tutorial-00-owl': ('assets/gallery-src/owl.jpg', 'Owl steps')}
ID = re.compile(r'^([a-z]+)-(\d\d)-([a-z0-9-]+)$')


def title_from(slug):
    return slug.replace('-', ' ').capitalize()


def main():
    sources = {key: (ROOT / path, title) for key, (path, title) in SEEDS.items()}
    skipped = []
    for path in sorted(SOURCE.glob('*')) if SOURCE.exists() else []:
        if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
            continue
        match = ID.match(path.stem.lower())
        if not match or match.group(1) not in dict(CATEGORIES):
            skipped.append(path.name)
            continue
        sources[path.stem.lower()] = (path, title_from(match.group(3)))
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
        print('Skipped (name must look like animals-01-fox.png):', ', '.join(skipped), file=sys.stderr)


if __name__ == '__main__':
    main()
