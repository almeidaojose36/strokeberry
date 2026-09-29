"""Brand kit (a Pro feature for small businesses): the drawing colour and a logo in the corner of exported videos."""
import re
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

CORNERS = ('bottom-right', 'bottom-left', 'top-right', 'top-left')
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


def logo_path(data_dir: Path, user_id: str):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', user_id)[:80]
    return data_dir / 'brand' / f'{safe}.png'


def save_logo(data_dir, user_id, raw: bytes):
    """Validate an uploaded logo and store it as a transparent PNG no larger than 600 px."""
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError('Please use a logo with fewer than 20 megapixels.')
            image = ImageOps.exif_transpose(image).convert('RGBA')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError('Use a PNG, JPG or WebP logo.')
    image.thumbnail((600, 600), Image.LANCZOS)
    path = logo_path(data_dir, user_id)
    path.parent.mkdir(exist_ok=True)
    image.save(path)
    return path


def hex_to_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
