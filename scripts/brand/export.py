#!/usr/bin/env python3
"""Exports the Strokeberry logo PNGs from the approved artwork in marketing/brand-sources/approved/.

    mascot-transparent.png   full mascot (approved v1 artwork)
    logo-cream.png           primary lockup on cream (approved v1 artwork)
    compact-mark.png         compact mark, cut from the approval sheet by approved_marks.py

Nothing is redrawn: files are only cropped, scaled, and placed on backgrounds. The wordmark on the
dark lockup is set in Bricolage Grotesque 800 with headless Chrome. Run:

    .venv/bin/python scripts/brand/approved_marks.py && .venv/bin/python scripts/brand/export.py
"""
import os
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "marketing/brand-sources/approved"
BRAND = ROOT / "frontend/public/brand"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FONTS = "https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,800&display=block"
PAPER = (255, 253, 248)


def shoot(html: str, width: int, height: int) -> Image.Image:
    """Screenshot an HTML snippet on a transparent background. Chrome can linger after saving, so stop it ourselves."""
    with tempfile.TemporaryDirectory() as tmp:
        page, out = Path(tmp) / "page.html", Path(tmp) / "out.png"
        page.write_text(html)
        proc = subprocess.Popen(
            [CHROME, "--headless=new", "--default-background-color=00000000", "--disable-gpu", "--hide-scrollbars",
             "--no-first-run", "--allow-file-access-from-files", "--force-device-scale-factor=1",
             f"--user-data-dir={tmp}/profile", f"--window-size={width},{height}", "--virtual-time-budget=6000",
             f"--screenshot={out}", page.as_uri()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            if out.exists() and out.stat().st_size:
                break
            time.sleep(0.5)
        time.sleep(0.5)
        proc.kill()
        return Image.open(out).convert("RGBA")


def trimmed(im: Image.Image) -> Image.Image:
    return im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())


def save(im: Image.Image, name: str, size=None) -> None:
    if size:
        im = im.resize(size if isinstance(size, tuple) else (size, size), Image.LANCZOS)
    im.save(BRAND / name)
    print(f"  {name}  {im.size[0]}×{im.size[1]}")


def on_square(mark: Image.Image, side: int, fill, inset: float) -> Image.Image:
    """Centre the mark on a square canvas, leaving `inset` of the side as margin on each edge."""
    canvas = Image.new("RGBA", (side, side), fill)
    inner = round(side * (1 - 2 * inset))
    m = mark.copy()
    m.thumbnail((inner, inner), Image.LANCZOS)
    canvas.alpha_composite(m, ((side - m.width) // 2, (side - m.height) // 2))
    return canvas


def rounded(im: Image.Image, radius: float) -> Image.Image:
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), round(im.width * radius), fill=255)
    out = im.copy()
    out.putalpha(mask)
    return out


print("Exporting PNGs to", BRAND.relative_to(ROOT))
compact = trimmed(Image.open(SRC / "compact-mark.png").convert("RGBA"))
mascot = trimmed(Image.open(SRC / "mascot-transparent.png").convert("RGBA"))

# Compact mark (site header, studio, social logo slot).
for side, name in [(512, "strokeberry-icon-512.png"), (1024, "strokeberry-icon-512@2x.png")]:
    save(on_square(compact, side, (0, 0, 0, 0), 0.02), name)
save(on_square(compact, 512, (0, 0, 0, 0), 0.0), "strokeberry-icon-small-512.png")
for side in (32, 64):
    save(on_square(compact, 512, (0, 0, 0, 0), 0.0), f"favicon-{side}.png", side)

# App icons: the approved 03 layout, the compact mark on a cream square.
app = on_square(compact, 1024, PAPER + (255,), 0.12).convert("RGB")
save(app, "strokeberry-app-icon-1024.png")
for side, name in [(512, "strokeberry-512.png"), (192, "strokeberry-192.png"), (180, "apple-touch-icon.png")]:
    save(app, name, side)
save(rounded(app.convert("RGBA"), 0.22), "strokeberry-app-icon-rounded-1024.png")

# Full mascot, transparent.
save(mascot, "strokeberry-mascot@2x.png")
save(mascot, "strokeberry-mascot.png", (mascot.width // 2, mascot.height // 2))

# Lockups: the approved cream lockup as supplied, and the same layout on dark (01 on the approval sheet).
light = Image.open(SRC / "logo-cream.png").convert("RGB")
save(light, "strokeberry-logo@2x.png")
save(light, "strokeberry-logo.png", (light.width // 2, light.height // 2))
with tempfile.TemporaryDirectory() as tmp:
    art = Path(tmp) / "mascot.png"
    mascot.save(art)
    dark = shoot(
        f"<link href='{FONTS}' rel='stylesheet'><style>html,body{{margin:0;background:#1B1B1B}}"
        f".w{{width:1774px;height:887px;display:flex;align-items:center;gap:30px;padding:0 60px;box-sizing:border-box;"
        f"font:800 200px 'Bricolage Grotesque';letter-spacing:-.03em;color:#FFF8EC}}</style>"
        f"<div class='w'><img src='{art.as_uri()}' style='height:660px'>strokeberry</div>", 1774, 887)
save(dark.convert("RGB"), "strokeberry-logo-on-dark@2x.png")
save(dark.convert("RGB"), "strokeberry-logo-on-dark.png", (887, 443))
