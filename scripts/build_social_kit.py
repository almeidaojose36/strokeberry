from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
OUT = ROOT / "marketing" / "social-kit"
BG = OUT / "assets" / "paper-campaign-background.png"

INK = "#1D1B1C"
RED = "#D92536"
GREEN = "#286347"
CREAM = "#FFF8EA"
WHITE = "#FFFFFF"
MUTED = "#756F68"
LINE = "#E5D8C3"

FONT = "/System/Library/Fonts/Avenir Next.ttc"


def font(size, weight="regular"):
    index = {"regular": 0, "medium": 2, "bold": 7, "heavy": 8}.get(weight, 0)
    try:
        return ImageFont.truetype(FONT, size=size, index=index)
    except OSError:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=size)


def fit_bg(size):
    image = Image.open(BG).convert("RGB")
    sw, sh = size
    scale = max(sw / image.width, sh / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    x = (image.width - sw) // 2
    y = (image.height - sh) // 2
    return image.crop((x, y, x + sw, y + sh)).convert("RGBA")


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def cover(path, size, focus=(0.5, 0.5)):
    image = Image.open(path).convert("RGB")
    scale = max(size[0] / image.width, size[1] / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    x = max(0, min(image.width - size[0], round((image.width - size[0]) * focus[0])))
    y = max(0, min(image.height - size[1], round((image.height - size[1]) * focus[1])))
    return image.crop((x, y, x + size[0], y + size[1])).convert("RGBA")


def add_card(canvas, image, box, radius=30, rotate=0):
    x, y, w, h = box
    image = image.resize((w, h), Image.Resampling.LANCZOS)
    mask = rounded_mask((w, h), radius)
    shadow = Image.new("RGBA", (w + 60, h + 70), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((30, 25, w + 29, h + 24), radius=radius, fill=(29, 27, 28, 48))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    card = Image.new("RGBA", (w + 60, h + 70), (0, 0, 0, 0))
    card.alpha_composite(shadow)
    card.paste(image, (30, 20), mask)
    if rotate:
        card = card.rotate(rotate, resample=Image.Resampling.BICUBIC, expand=True)
    canvas.alpha_composite(card, (x - 30, y - 20))


def text(draw, xy, value, size, color=INK, weight="regular", spacing=4, anchor=None):
    draw.multiline_text(xy, value, font=font(size, weight), fill=color, spacing=spacing, anchor=anchor)


def pill(draw, xy, label, fill=RED, fg=WHITE, size=24, pad=(24, 13)):
    f = font(size, "bold")
    box = draw.textbbox((0, 0), label, font=f)
    w, h = box[2] - box[0] + 2 * pad[0], box[3] - box[1] + 2 * pad[1]
    x, y = xy
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=fill)
    draw.text((x + w / 2, y + h / 2 - 1), label, font=f, fill=fg, anchor="mm")
    return w, h


def add_logo(canvas, xy, width, dark=False):
    name = "strokeberry-logo-on-dark.png" if dark else "strokeberry-logo.png"
    logo = Image.open(PUBLIC / "brand" / name).convert("RGBA")
    logo.thumbnail((width, width), Image.Resampling.LANCZOS)
    canvas.alpha_composite(logo, xy)


def save(canvas, name):
    path = OUT / name
    canvas.convert("RGB").save(path, quality=95, optimize=True)
    return path


def profile():
    c = Image.new("RGBA", (1024, 1024), RED)
    d = ImageDraw.Draw(c)
    for r, alpha in [(430, 18), (350, 12), (280, 8)]:
        d.ellipse((512-r, 512-r, 512+r, 512+r), outline=(255,255,255,alpha), width=3)
    icon = Image.open(PUBLIC / "brand" / "strokeberry-icon-512.png").convert("RGBA")
    icon = icon.resize((610, 610), Image.Resampling.LANCZOS)
    c.alpha_composite(icon, (207, 207))
    save(c, "profile-1024.png")


def banner(name, size, safe, headline_size):
    c = fit_bg(size)
    d = ImageDraw.Draw(c)
    sx, sy, sw, sh = safe
    add_logo(c, (sx, sy + 10), min(420, int(sw * .28)))
    text(d, (sx, sy + int(sh * .36)), "Turn any image into a\nhand-drawn video.", headline_size, weight="bold", spacing=2)
    pill(d, (sx, sy + int(sh * .76)), "TRY 3 VIDEOS FREE", size=max(14, headline_size // 4))
    art_w = int(min(sh * 1.12, sw * .34))
    art_h = art_w
    img = cover(PUBLIC / "showcase" / "strawberry-sheet.jpg", (art_w, art_h))
    add_card(c, img, (sx + sw - art_w, sy + (sh - art_h) // 2, art_w, art_h), radius=max(16, art_w // 18), rotate=-2)
    save(c, name)


def instagram_launch():
    c = fit_bg((1080, 1080)); d = ImageDraw.Draw(c)
    add_logo(c, (70, 62), 330)
    text(d, (70, 208), "Still image.\nHand-drawn story.", 84, weight="bold", spacing=-2)
    text(d, (73, 405), "Turn artwork, logos and drawing tutorials\ninto satisfying speedpaint videos.", 30, MUTED, "medium", 8)
    img = cover(PUBLIC / "showcase" / "strawberry-sheet.jpg", (520, 520))
    add_card(c, img, (505, 500, 520, 520), radius=40, rotate=-2)
    pill(d, (70, 750), "LAUNCH SPECIAL", size=23)
    text(d, (70, 832), "3 videos free", 58, weight="bold")
    text(d, (73, 904), "40% off your first 3 months", 27, GREEN, "bold")
    save(c, "instagram-launch-1080x1080.png")


def four_steps():
    c = Image.new("RGBA", (1080, 1080), CREAM); d = ImageDraw.Draw(c)
    text(d, (70, 64), "FOUR STEPS. ONE VIDEO.", 21, RED, "bold")
    text(d, (70, 110), "From guide lines\nto final color.", 76, weight="bold", spacing=-2)
    img = cover(PUBLIC / "showcase" / "strawberry-sheet.jpg", (820, 820))
    add_card(c, img, (390, 330, 620, 620), radius=38, rotate=1)
    steps = [("01", "Guides"), ("02", "Outline"), ("03", "Details"), ("04", "Color")]
    for i, (num, label) in enumerate(steps):
        y = 440 + i * 112
        d.ellipse((70, y, 126, y + 56), fill=RED if i == 3 else INK)
        text(d, (98, y + 28), num, 18, WHITE, "bold", anchor="mm")
        text(d, (148, y + 28), label, 27, weight="bold", anchor="lm")
    text(d, (70, 990), "strokeberry", 26, GREEN, "bold")
    save(c, "instagram-four-steps-1080x1080.png")


def story():
    c = fit_bg((1080, 1920)); d = ImageDraw.Draw(c)
    add_logo(c, (70, 80), 350)
    pill(d, (70, 220), "NOW IN EARLY ACCESS", size=23)
    text(d, (70, 320), "Your drawing\ndeserves to move.", 92, weight="bold", spacing=-5)
    text(d, (74, 555), "Upload an image. Pick a style.\nExport a hand-drawn video.", 34, MUTED, "medium", 10)
    img = cover(PUBLIC / "showcase" / "owl-sheet.jpg", (800, 800))
    add_card(c, img, (140, 770, 800, 800), radius=48, rotate=-2)
    d.rounded_rectangle((70, 1670, 1010, 1825), radius=48, fill=INK)
    text(d, (540, 1722), "TRY YOUR FIRST 3 VIDEOS FREE", 31, WHITE, "bold", anchor="mm")
    text(d, (540, 1778), "strokeberry.com", 25, "#DCCDB9", "medium", anchor="mm")
    save(c, "story-launch-1080x1920.png")


def landscape():
    c = fit_bg((1200, 627)); d = ImageDraw.Draw(c)
    add_logo(c, (58, 46), 310)
    text(d, (58, 165), "Make your pictures\ncome to life.", 68, weight="bold", spacing=-4)
    text(d, (61, 340), "Turn any image into a beautifully\nhand-drawn video.", 27, MUTED, "medium", 7)
    pill(d, (58, 465), "TRY 3 VIDEOS FREE", size=21)
    img = cover(PUBLIC / "showcase" / "owl-sheet.jpg", (500, 500))
    add_card(c, img, (660, 64, 500, 500), radius=34, rotate=2)
    save(c, "launch-post-1200x627.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    profile()
    banner("youtube-banner-2560x1440.png", (2560, 1440), (507, 508, 1546, 423), 82)
    banner("x-banner-1500x500.png", (1500, 500), (90, 55, 1320, 390), 58)
    banner("facebook-cover-1640x624.png", (1640, 624), (90, 70, 1460, 480), 64)
    banner("linkedin-banner-1128x191.png", (1128, 191), (48, 22, 1032, 147), 30)
    instagram_launch()
    four_steps()
    story()
    landscape()
    print(f"Created social kit in {OUT}")


if __name__ == "__main__":
    main()
