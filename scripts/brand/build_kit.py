#!/usr/bin/env python3
"""Builds the Strokeberry brand kit (edition 1.1) from the live brand assets.

Everything is copied from the same files the website, studio and launch video use, so the kit
cannot drift from the product. Run after scripts/brand/logo.py, scripts/brand/export.py and
scripts/render-social.sh:

    .venv/bin/python scripts/brand/build_kit.py

Output: marketing/brand-kit-v1.1/ and marketing/Strokeberry-brand-kit-v1.1.zip
"""
import html
import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / "frontend/public/brand"
SOCIAL = ROOT / "marketing/social/out"
APPROVED = ROOT / "marketing/brand-sources/approved"  # the approved artwork (edition 1 and the approval sheet)
KIT = ROOT / "marketing/brand-kit-v1.1"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
EDITION = "Edition 1.1 · September 2026"
TAGLINE = "Your images. Drawn to life."

# One palette for everything. "use" is shown in the guidelines and written to the tokens.
PALETTE = [
    ("paper", "Paper", "#FFF8EC", "Main background"),
    ("charcoal", "Charcoal", "#1B1B1B", "Text, outlines, dark layouts"),
    ("strawberry", "Strawberry", "#EC2D34", "Brand accent, large shapes"),
    ("strawberry-button", "Strawberry button", "#D42630", "Buttons with white text"),
    ("strawberry-text", "Strawberry text", "#C81E2A", "Small red text on paper"),
    ("teal", "Teal", "#00BEC8", "Headphones, gloves, accents"),
    ("teal-deep", "Teal deep", "#0096A0", "Teal fills behind white text"),
    ("leaf", "Leaf", "#69B644", "Leaf crown, success"),
    ("pencil", "Pencil", "#FABE3A", "Pencil, highlights, marker swash"),
    ("blush", "Blush", "#FD8F90", "Cheeks, eraser, soft accents"),
]
FONT_DISPLAY, FONT_BODY = "Bricolage Grotesque", "Figtree"
PX = 9525  # EMU per CSS pixel at 96 dpi


def copy(src: Path, dst: str) -> None:
    target = KIT / dst
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)


# ---------------------------------------------------------------- files
def assemble() -> None:
    if KIT.exists():
        shutil.rmtree(KIT)
    KIT.mkdir(parents=True)
    shutil.copytree(ROOT / "marketing/brand-sources/fonts", KIT / "fonts")
    pngs = {
        "strokeberry-logo@2x.png": "logos/png/strokeberry-logo-on-light.png",
        "strokeberry-logo-on-dark@2x.png": "logos/png/strokeberry-logo-on-dark.png",
        "strokeberry-icon-512@2x.png": "logos/png/strokeberry-logo-mark-1024.png",
        "strokeberry-icon-512.png": "logos/png/strokeberry-logo-mark-512.png",
        "strokeberry-mascot@2x.png": "logos/png/strokeberry-mascot.png",
        "strokeberry-app-icon-1024.png": "logos/app-icons/app-icon-1024.png",
        "strokeberry-app-icon-rounded-1024.png": "logos/app-icons/app-icon-rounded-1024.png",
        "strokeberry-512.png": "logos/app-icons/app-icon-512.png",
        "strokeberry-192.png": "logos/app-icons/app-icon-192.png",
        "apple-touch-icon.png": "logos/app-icons/apple-touch-icon-180.png",
        "favicon-64.png": "logos/app-icons/favicon-64.png",
        "favicon-32.png": "logos/app-icons/favicon-32.png",
    }
    for src, dst in pngs.items():
        copy(BRAND / src, dst)
    # The approved originals, unchanged, for reference and print.
    copy(APPROVED / "approval-sheet.webp", "logos/approved-originals/approval-sheet.webp")
    copy(APPROVED / "mascot-transparent.png", "logos/approved-originals/mascot-transparent.png")
    copy(APPROVED / "logo-cream.png", "logos/approved-originals/logo-cream.png")
    socials = {
        "profile-sun.png": "social/profile-picture-yellow.png",
        "profile-cream.png": "social/profile-picture-cream.png",
        "youtube-banner.png": "social/banners/youtube-2560x1440.png",
        "x-header.png": "social/banners/x-1500x500.png",
        "facebook-cover.png": "social/banners/facebook-1640x624.png",
        "linkedin-company-cover.png": "social/banners/linkedin-1128x191.png",
        "pinterest-cover.png": "social/banners/pinterest-1920x1080.png",
        "highlight-gallery.png": "social/instagram-highlights/gallery.png",
        "highlight-tutorials.png": "social/instagram-highlights/tutorials.png",
        "highlight-tips.png": "social/instagram-highlights/tips.png",
        "highlight-new.png": "social/instagram-highlights/new.png",
    }
    for src, dst in socials.items():
        copy(SOCIAL / src, dst)
    copy(APPROVED / "banner-dark.png", "social/banners/campaign-banner-dark.png")
    copy(BRAND / "og-image.png", "social/website-share-image-1200x630.png")


def tokens() -> None:
    out = KIT / "brand-tokens"
    out.mkdir(parents=True, exist_ok=True)
    css = [":root {"] + [f"  --strokeberry-{k}: {hexv};" for k, _, hexv, _ in PALETTE]
    css += [f"  --strokeberry-font-display: '{FONT_DISPLAY}', 'Arial Black', sans-serif;",
            f"  --strokeberry-font-body: '{FONT_BODY}', Arial, sans-serif;", "}"]
    (out / "colors.css").write_text("\n".join(css) + "\n")
    (out / "tokens.json").write_text(json.dumps({
        "colors": {k: {"hex": v, "use": use} for k, _, v, use in PALETTE},
        "fonts": {"display": {"family": FONT_DISPLAY, "weights": [700, 800], "use": "Headlines and the wordmark"},
                  "body": {"family": FONT_BODY, "weights": [400, 500, 600, 700], "use": "Body copy, interface, captions"}},
        "tagline": TAGLINE,
    }, indent=2) + "\n")


def docs() -> None:
    (KIT / "README.md").write_text(f"""# Strokeberry brand kit — {EDITION}

{TAGLINE}

Edition 1.1 matches exactly what the website, studio and launch video use. It replaces edition 1,
which had a different teal and Arial type. The logo artwork is unchanged from edition 1 and the
approval sheet: every logo file is cut or scaled from the approved art, never redrawn.

## The logo system
| Use | File | Where |
|---|---|---|
| **Primary logo** | `logos/png/strokeberry-logo-on-light.png` / `-on-dark.png` (full mascot + wordmark) | Website, documents, banners |
| **Full mascot** | `logos/png/strokeberry-mascot.png` (transparent) | **Everywhere**: headers, hero sections, profile pictures, video, stickers, merch |
| **Compact logo** | `logos/png/strokeberry-logo-mark-*.png` (transparent) | **Small places only**: favicons, app icons, avatars and badges under ~48 px |

**Rule:** use the full mascot on everything. Switch to the compact logo only where the full body would be too small to read.
| Approved originals | `logos/approved-originals/` | The source artwork as approved |

All logos are PNG artwork. For large print or embroidery, have the approved art professionally
vector-traced from `logos/approved-originals/`; the compact logo source is small (from the approval
sheet), so ask for a high-resolution export of it if you have the original file.
The wordmark is lowercase **strokeberry** set in Bricolage Grotesque ExtraBold (800), tracking −2%.

## Colour
See `brand-tokens/colors.css` or `tokens.json`. Use Strawberry button (#D42630) behind white text and
Strawberry text (#C81E2A) for small red text; the base Strawberry red is too light for small text.

## Type
- **Bricolage Grotesque** 700–800 for headlines and the wordmark.
- **Figtree** 400–700 for body copy, interface and captions.
Both are free under the SIL Open Font License; the desktop files are in `fonts/`. Install them before
editing the PowerPoint. Without them, use Arial Black and Arial as stand-ins.

## Social
Profile pictures use the full mascot, as in edition 1 (`social/profile-picture-cream.png`). Banners are provided at each platform's exact size, with text
kept inside the area every device shows. `social/account-copy.md` has bios and launch captions.

## Rebuilding
Everything here is generated from the project:
`.venv/bin/python scripts/brand/approved_marks.py && .venv/bin/python scripts/brand/export.py && scripts/render-social.sh && .venv/bin/python scripts/brand/build_kit.py`

No domain or social handle ownership is assumed. Publish offers only once billing implements them.
""")
    copy_text = (ROOT / "marketing/social/account-copy.md").read_text()
    copy_text = copy_text.replace("Explore Strokeberry below.", "Try it free below.")
    (KIT / "social/account-copy.md").write_text(copy_text)


# ---------------------------------------------------------------- guidelines
def T(x, y, w, h, text, size, color="#1B1B1B", font="body", weight=400, align="left"):
    return ("text", x, y, w, h, text, size, color, font, weight, align)


def I(x, y, w, h, path):
    return ("img", x, y, w, h, str(path))


def R(x, y, w, h, fill, radius=0, line=None):
    return ("rect", x, y, w, h, fill, radius, line)


def footer(n, dark=False):
    return T(64, 670, 1100, 24, f"STROKEBERRY  /  BRAND GUIDELINES  /  {n:02d}", 12, "#9A948B" if dark else "#8A8174")


def title(text, dark=False):
    return T(64, 46, 1150, 80, text, 44, "#FFF8EC" if dark else "#1B1B1B", "display", 800)


def slides():
    k = KIT
    s = []
    s.append(("#1B1B1B", [I(0, 90, 1280, 427, k / "social/banners/campaign-banner-dark.png"),
                          T(64, 560, 1100, 60, "Brand guidelines", 44, "#FFF8EC", "display", 800),
                          T(66, 622, 1100, 30, EDITION, 20, "#FFF8EC"), footer(1, True)]))
    s.append(("#FFF8EC", [title("The brand"),
                          T(64, 170, 700, 190, "Your images.\nDrawn to life.", 68, font="display", weight=800),
                          T(64, 395, 660, 110, "Strokeberry turns still artwork, logos and drawing tutorials into videos that reveal every stroke.", 26),
                          T(64, 515, 660, 90, "For creators, teachers, Etsy sellers and small brands who want to show how an image comes together.", 21, "#5B544A"),
                          I(800, 130, 420, 470, k / "logos/png/strokeberry-mascot.png"), footer(2)]))
    s.append(("#FFF8EC", [title("The logo system"),
                          R(64, 150, 360, 330, "#FFFFFF", 18), I(124, 165, 240, 250, k / "logos/png/strokeberry-mascot.png"),
                          T(84, 420, 320, 50, "Full mascot", 24, font="display", weight=800, align="center"),
                          T(64, 495, 360, 110, "Use on everything: headers, banners, profiles, video, merch.", 19, align="center"),
                          R(460, 150, 360, 330, "#FFFFFF", 18), I(520, 170, 240, 240, k / "logos/png/strokeberry-logo-mark-512.png"),
                          T(480, 420, 320, 50, "Compact logo", 24, font="display", weight=800, align="center"),
                          T(460, 495, 360, 110, "Small places only: favicons, avatars, tiny badges.", 19, align="center"),
                          R(856, 150, 360, 330, "#FFFFFF", 18), I(956, 190, 200, 200, k / "logos/app-icons/app-icon-rounded-1024.png"),
                          T(876, 420, 320, 50, "App icon", 24, font="display", weight=800, align="center"),
                          T(856, 495, 360, 110, "The compact logo on Paper: app icon and favicon.", 19, align="center"),
                          footer(3)]))
    s.append(("#FFF8EC", [title("Primary lockup"),
                          I(64, 150, 560, 280, k / "logos/png/strokeberry-logo-on-light.png"),
                          I(656, 150, 560, 280, k / "logos/png/strokeberry-logo-on-dark.png"),
                          T(64, 470, 1120, 140, "The approved lockup: the full mascot on the left, lowercase strokeberry in Bricolage Grotesque ExtraBold on the right. Charcoal wordmark on light backgrounds, Paper on dark.", 20),
                          footer(4)]))
    s.append(("#FFF8EC", [title("The mascot"),
                          I(70, 140, 500, 480, k / "logos/png/strokeberry-mascot.png"),
                          T(640, 170, 560, 55, "A creator with personality", 32, font="display", weight=800),
                          T(640, 250, 560, 360, "The pencil explains what Strokeberry does.\n\nThe headphones give it a creator's vibe.\n\nThe cheerful face makes the product approachable.\n\nKeep the pencil and headphones together in every use.", 22),
                          footer(5)]))
    s.append(("#FFF8EC", [title("Clear space and sizes"),
                          R(64, 150, 560, 380, "#FFFFFF", 18), R(114, 200, 460, 280, "#FFFFFF", 12, "#EC2D34"),
                          I(144, 215, 400, 250, k / "logos/png/strokeberry-mascot.png"),
                          T(84, 545, 520, 70, "Clear space on every side: the width of one ear-cup.", 19),
                          T(680, 170, 540, 440, "Minimum sizes\n\nFull mascot: 48 px tall (below that, use the compact logo)\nFull lockup: 140 px wide\nCompact logo: 16 px\n\nNever stretch, rotate, recolour or add effects. Use the largest PNG supplied; never enlarge a small one.", 21),
                          footer(6)]))
    colors = []
    for i, (_, name, hexv, use) in enumerate(PALETTE):
        x, y = 64 + (i % 5) * 234, 150 + (i // 5) * 250
        line = "#E2D1B2" if hexv in ("#FFF8EC",) else None
        colors += [R(x, y, 210, 110, hexv, 14, line), T(x, y + 120, 210, 30, name, 18, font="display", weight=800),
                   T(x, y + 150, 210, 26, hexv, 17), T(x, y + 178, 210, 50, use, 15, "#5B544A")]
    s.append(("#FFF8EC", [title("Colour palette")] + colors + [footer(7)]))
    s.append(("#FFF8EC", [title("Typography"),
                          T(64, 150, 380, 220, "Aa", 170, font="display", weight=800),
                          T(470, 160, 740, 50, "Bricolage Grotesque", 36, font="display", weight=800),
                          T(472, 214, 740, 60, "Weights 700–800. Headlines, campaign lines and the wordmark. Tight tracking (−2% to −3%).", 20),
                          T(470, 318, 740, 50, "Figtree", 36, weight=700),
                          T(472, 372, 740, 60, "Weights 400–700. Body copy, interface text, captions and buttons.", 20),
                          T(64, 500, 1150, 120, "Both fonts are free (SIL Open Font License); desktop files are in the kit's fonts folder. Where they can't be installed, use Arial Black for headlines and Arial for text.", 20, "#5B544A"),
                          footer(8)]))
    s.append(("#FFF8EC", [title("Brand voice"),
                          T(64, 150, 1100, 60, "Warm, clear and specific", 34, font="display", weight=800),
                          T(64, 240, 1120, 170, "“Turn your drawing into a video.”\n“Preview every stroke before you export.”\n“Four drawing steps. One continuous video.”", 28),
                          T(64, 460, 1130, 130, "Explain the action and the result in short sentences. Avoid guaranteed render times, unsupported AI claims and promises about features that are not live. Strokeberry does not use generative AI on customer images.", 22, "#5B544A"),
                          footer(9)]))
    s.append(("#FFF8EC", [title("Social identity"),
                          I(64, 150, 400, 400, k / "social/profile-picture-cream.png"),
                          T(520, 170, 700, 50, "Profile picture: the full mascot", 30, font="display", weight=800),
                          T(520, 240, 690, 200, "Use the full mascot on Paper (or Pencil yellow) for every account, centred so the circle crop keeps the pencil and headphones.", 22),
                          T(520, 440, 690, 120, "Display name: Strokeberry\nSuggested handle: @strokeberry (availability not checked)\nBio line: Your images. Drawn to life.", 20, "#5B544A"),
                          footer(10)]))
    s.append(("#FFF8EC", [title("Banners"),
                          I(64, 150, 560, 187, k / "social/banners/x-1500x500.png"),
                          I(656, 150, 560, 187, k / "social/banners/campaign-banner-dark.png"),
                          I(64, 360, 560, 213, k / "social/banners/facebook-1640x624.png"),
                          T(656, 370, 560, 250, "Each platform's banner is supplied at its exact size, with the message kept inside the area every phone, desktop and TV shows, clear of the profile picture. Keep banners evergreen: no prices or offers.", 20),
                          footer(11)]))
    s.append(("#FFF8EC", [title("Brand consistency"),
                          T(64, 150, 520, 55, "Always", 32, font="display", weight=800),
                          T(64, 220, 540, 330, "Keep the pencil and headphones.\nUse the full mascot everywhere; compact only when small.\nUse the approved palette values.\nUse the approved artwork, never a redraw.", 22),
                          T(680, 150, 500, 55, "Avoid", 32, "#C81E2A", "display", 800),
                          T(680, 220, 540, 330, "Retyping the wordmark in another font.\nRedrawing or tracing the mascot in-house.\nStretching, rotating or recolouring.\nDark text on dark artwork.", 22),
                          footer(12)]))
    s.append(("#FFF8EC", [title("Launch messaging"),
                          T(64, 150, 1100, 50, "Evergreen message", 28, font="display", weight=800),
                          T(64, 210, 1130, 80, "Turn any image into a hand-drawn video.", 36),
                          T(64, 330, 1100, 50, "Offer copy (only once billing supports it)", 28, font="display", weight=800),
                          T(64, 390, 1100, 100, "Try your first 3 videos free.\nSave 40% on your first 3 months.", 28),
                          T(64, 540, 1120, 70, "Publish offer copy only when checkout, credits, watermark rules and eligibility match the offer.", 19, "#5B544A"),
                          footer(13)]))
    s.append(("#FFF8EC", [title("Files and production"),
                          T(64, 150, 540, 50, "In this kit", 28, font="display", weight=800),
                          T(64, 210, 540, 400, "Approved logo artwork (originals + PNG exports)\nPNG lockups for light and dark\nApp icons and favicons\nProfile pictures and platform banners\nInstagram highlight covers\nWebsite share image\nColour tokens (CSS, JSON)\nBricolage Grotesque and Figtree fonts\nBios and launch captions", 19),
                          T(680, 150, 540, 50, "Production notes", 28, font="display", weight=800),
                          T(680, 210, 540, 400, "All logo files come from the approved artwork, cropped and scaled, never redrawn.\n\nFor large print or embroidery, have the approved originals professionally vector-traced.\n\nEverything is regenerated from the project's scripts, so the kit always matches the product.", 19),
                          footer(14)]))
    return s


def guidelines_html(deck) -> str:
    fonts = f"""@font-face{{font-family:'{FONT_DISPLAY}';src:url('{(KIT / "fonts/BricolageGrotesque[opsz,wdth,wght].ttf").as_uri()}');font-weight:200 800}}
@font-face{{font-family:'{FONT_BODY}';src:url('{(KIT / "fonts/Figtree[wght].ttf").as_uri()}');font-weight:300 900}}"""
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><style>{fonts}"
             "@page{size:1280px 720px;margin:0}body{margin:0}.s{position:relative;width:1280px;height:720px;overflow:hidden;page-break-after:always}"
             ".s *{position:absolute;box-sizing:border-box;margin:0}.t{white-space:pre-wrap;line-height:1.25}"
             "img{object-fit:contain}</style></head><body>"]
    for bg, els in deck:
        parts.append(f"<div class='s' style='background:{bg}'>")
        for e in els:
            if e[0] == "text":
                _, x, y, w, h, text, size, color, font, weight, align = e
                fam = FONT_DISPLAY if font == "display" else FONT_BODY
                ls = "-.025em" if font == "display" else "0"
                parts.append(f"<div class='t' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;font:{weight} {size}px/{1.05 if font == 'display' else 1.35} \"{fam}\";letter-spacing:{ls};color:{color};text-align:{align}'>{html.escape(text)}</div>")
            elif e[0] == "img":
                _, x, y, w, h, path = e
                parts.append(f"<img src='{Path(path).as_uri()}' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px'>")
            else:
                _, x, y, w, h, fill, radius, line = e
                border = f"border:3px dashed {line};" if line == "#EC2D34" else (f"border:2px solid {line};" if line else "")
                parts.append(f"<div style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{fill};border-radius:{radius}px;{border}'></div>")
        parts.append("</div>")
    parts.append("</body></html>")
    return "".join(parts)


def guidelines_pdf(page: Path, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out.unlink(missing_ok=True)
        proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--allow-file-access-from-files",
                                 f"--user-data-dir={tmp}", "--no-pdf-header-footer", "--virtual-time-budget=8000",
                                 f"--print-to-pdf={out}", page.as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(80):
            if out.exists() and out.stat().st_size:
                time.sleep(1)
                break
            time.sleep(0.5)
        proc.kill()


def rgb(hexv: str) -> RGBColor:
    return RGBColor.from_string(hexv.lstrip("#"))


def guidelines_pptx(deck, out: Path) -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(1280 * PX), Emu(720 * PX)
    blank = prs.slide_layouts[6]
    for bg, els in deck:
        slide = prs.slides.add_slide(blank)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = rgb(bg)
        for e in els:
            if e[0] == "rect":
                _, x, y, w, h, fill, radius, line = e
                shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                                               Emu(x * PX), Emu(y * PX), Emu(w * PX), Emu(h * PX))
                if radius:
                    shape.adjustments[0] = min(0.5, radius / min(w, h))
                shape.fill.solid(); shape.fill.fore_color.rgb = rgb(fill)
                if line:
                    shape.line.color.rgb = rgb(line); shape.line.width = Pt(2)
                else:
                    shape.line.fill.background()
                shape.shadow.inherit = False
            elif e[0] == "img":
                _, x, y, w, h, path = e
                iw, ih = Image.open(path).size
                scale = min(w / iw, h / ih)
                dw, dh = iw * scale, ih * scale
                slide.shapes.add_picture(path, Emu(int((x + (w - dw) / 2) * PX)), Emu(int((y + (h - dh) / 2) * PX)),
                                         Emu(int(dw * PX)), Emu(int(dh * PX)))
            else:
                _, x, y, w, h, text, size, color, font, weight, align = e
                if not text:
                    continue
                box = slide.shapes.add_textbox(Emu(x * PX), Emu(y * PX), Emu(w * PX), Emu(h * PX))
                tf = box.text_frame
                tf.word_wrap = True
                tf.vertical_anchor = MSO_ANCHOR.TOP
                for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
                    setattr(tf, side, 0)
                for i, line_text in enumerate(text.split("\n")):
                    para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    para.alignment = {"left": 1, "center": 2}[align]
                    run = para.add_run()
                    run.text = line_text
                    run.font.size = Pt(size * 0.75)
                    run.font.bold = weight >= 700
                    run.font.name = FONT_DISPLAY if font == "display" else FONT_BODY
                    run.font.color.rgb = rgb(color)
    prs.save(out)


def main() -> None:
    assemble()
    tokens()
    docs()
    deck = slides()
    gdir = KIT / "guidelines"
    gdir.mkdir(parents=True, exist_ok=True)
    page = gdir / "guidelines-source.html"
    page.write_text(guidelines_html(deck))
    guidelines_pdf(page, gdir / "Strokeberry-brand-guidelines.pdf")
    guidelines_pptx(deck, gdir / "Strokeberry-brand-guidelines.pptx")
    page.unlink()  # the source is this script; the page embeds local file paths
    zpath = ROOT / "marketing/Strokeberry-brand-kit-v1.1.zip"
    zpath.unlink(missing_ok=True)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(KIT.rglob("*")):
            if f.is_file() and f.name != ".DS_Store":
                z.write(f, Path("Strokeberry-brand-kit-v1.1") / f.relative_to(KIT))
    files = [f for f in KIT.rglob("*") if f.is_file()]
    print(f"Built {KIT.relative_to(ROOT)} ({len(files)} files) and {zpath.relative_to(ROOT)} ({zpath.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
