"""The "Start from an example" library: ready-made illustrations anyone can turn into a video.

Images and the manifest live in frontend/public/library/ (built by scripts/gallery/ingest.py), so the
browser loads thumbnails as ordinary static files and the server copies the full image into a new project.
"""
import json
from pathlib import Path

from fastapi import HTTPException

LIBRARY = Path(__file__).resolve().parent.parent / 'frontend' / 'public' / 'library'
_cache = {'mtime': None, 'data': None}


def manifest():
    path = LIBRARY / 'library.json'
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {'categories': [], 'items': []}
    if _cache['mtime'] != mtime:
        _cache['data'] = json.loads(path.read_text())
        _cache['mtime'] = mtime
    return _cache['data']


def items():
    data = manifest()
    return {'categories': data.get('categories', []),
            'items': [dict(item, image=f"/library/{item['image']}", thumb=f"/library/{item['thumb']}")
                      for item in data.get('items', [])]}


def find(item_id):
    for item in manifest().get('items', []):
        if item['id'] == item_id:
            path = LIBRARY / item['image']
            if path.is_file():
                return item, path
    raise HTTPException(404, 'That example is no longer available.')
