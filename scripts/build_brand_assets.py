from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "frontend" / "public" / "brand"
TMP = ROOT / ".brand-render"
TMP.mkdir(exist_ok=True)


def render_svg(name, size):
    source = BRAND / name
    subprocess.run(["qlmanage", "-t", "-s", str(size), "-o", str(TMP), str(source)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return Image.open(TMP / f"{name}.png").convert("RGBA")


def remove_white_canvas(image):
    # Quick Look flattens transparent SVGs onto white. Recover only the edge-connected
    # white canvas; enclosed white eye highlights remain intact.
    rgb = image.convert("RGB")
    pixels = rgb.load()
    background = Image.new("L", image.size, 0)
    background_pixels = background.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = pixels[x, y]
            if r > 245 and g > 245 and b > 245:
                background_pixels[x, y] = 255
    ImageDraw.floodfill(background, (0, 0), 128, thresh=0)
    alpha = background.point(lambda value: 0 if value == 128 else 255)
    result = image.copy()
    result.putalpha(alpha)
    return result


def wordmark(icon, dark=False):
    canvas = Image.new("RGBA", (1119, 187), (0, 0, 0, 0))
    icon = icon.resize((154, 154), Image.Resampling.LANCZOS)
    canvas.alpha_composite(icon, (7, 16))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype("/System/Library/Fonts/Avenir Next.ttc", 118, index=8)
    draw.text((178, 91), "strokeberry", font=font, fill="#FFF8EC" if dark else "#1D1B1C", anchor="lm")
    return canvas


def main():
    icon = remove_white_canvas(render_svg("strokeberry-icon.svg", 1024))
    app = render_svg("strokeberry-icon-app.svg", 1024)
    icon.resize((512, 512), Image.Resampling.LANCZOS).save(BRAND / "strokeberry-icon-512.png")
    app.save(BRAND / "strokeberry-app-icon-1024.png")
    app.resize((192, 192), Image.Resampling.LANCZOS).save(BRAND / "strokeberry-192.png")
    app.resize((180, 180), Image.Resampling.LANCZOS).save(BRAND / "apple-touch-icon.png")
    app.resize((32, 32), Image.Resampling.LANCZOS).save(ROOT / "frontend" / "public" / "favicon-32.png")
    wordmark(icon).save(BRAND / "strokeberry-logo.png")
    wordmark(icon, dark=True).save(BRAND / "strokeberry-logo-on-dark.png")
    print("Regenerated Strokeberry vector-derived brand assets")


if __name__ == "__main__":
    main()
