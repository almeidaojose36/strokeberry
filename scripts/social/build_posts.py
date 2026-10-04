"""Build ready-to-post Reels and carousels for the 30-day social plan.

    .venv/bin/python scripts/social/build_posts.py reel  <id> ...      (ids from PLAN below)
    .venv/bin/python scripts/social/build_posts.py carousel <id> ...

Reels: 1080x1920, drawn by Strokeberry like a Pro export, with
  - a designed first frame that Instagram uses as the cover (the finished picture with a title, or a "?" card for
    guessing clips, so the answer isn't spoiled),
  - an original background track from marketing/music/ (scripts/social/generate_music.py), faded in and out,
  - the "Made with Strokeberry" end card.
Carousels: 1080x1350 slides showing one picture's journey (original -> lines -> color) plus a call to action.
Copy uses US spelling: the audience is the United States and Canada.
Output: marketing/social/posts/<id>/ (reel.mp4, cover.jpg, slide-1.jpg ...).
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts' / 'social'))

from render_showcase import make  # noqa: E402

HERO, LIBRARY, HOME = ROOT / 'assets' / 'hero-src', ROOT / 'frontend' / 'public' / 'library', ROOT / 'assets' / 'interiors-src'
SPORTS = ROOT / 'assets' / 'sports-src'
MUSIC, OUT = ROOT / 'marketing' / 'music', ROOT / 'marketing' / 'social' / 'posts'
FONT = ROOT / 'backend' / 'assets' / 'Figtree.ttf'
MASCOT = ROOT / 'frontend' / 'public' / 'brand' / 'strokeberry-mascot@2x.png'
CREAM, INK, BERRY, TEAL, SUN = (255, 248, 236), (27, 27, 27), (200, 30, 42), (0, 190, 200), (250, 190, 58)
COVER_SECONDS = .5

# id: source image, style, hand, canvas, seconds (or tutorial step seconds), cover title (None = "?" card), track
PLAN = {
    'skincare': (HERO / 'skincare-1.jpg', 'ink', 'light', 'paper', 22, 'Skincare launch, drawn by hand', 'soul-lounge-2'),
    'fashion': (HERO / 'fashion-2.jpg', 'ink', 'dark', 'paper', 20, 'From sketch to product shot', 'funk-bounce-1'),
    'cafe': (HERO / 'cafe-1.jpg', 'ink', 'medium', 'greenboard', 24, 'Your café logo, on a chalkboard', 'autumn-acoustic-1'),
    'classroom': (HERO / 'lesson-1.jpg', 'ink', 'dark', 'blackboard', 24, 'Story time, drawn on the board', 'dreamy-indie-2'),
    'owl-lesson': (LIBRARY / 'tutorial-00-owl.jpg', 'ink', 'light', 'paper', [6, 8, 8, 10], 'How to draw an owl in 4 steps', 'future-bass-1'),
    'dino-lesson': (LIBRARY / 'tutorial-02-dinosaur.jpg', 'ink', 'medium', 'paper', [6, 8, 8, 10], 'How to draw a dinosaur in 4 steps', 'soft-piano-1'),
    'house': (HERO / 'house-1.jpg', 'ink', 'medium', 'paper', 24, 'Just listed, sketched by hand', 'soul-lounge-1'),
    'listed': (HERO / 'house-2.jpg', 'ink', 'light', 'paper', 22, 'A listing post nobody else has', 'autumn-acoustic-2'),
    'creator': (HERO / 'creator-2.jpg', 'ink', 'dark', 'paper', 18, 'Your channel intro in 60 seconds', 'dreamy-indie-1'),
    'living-room': (HOME / 'livingroom-2.jpg', 'ink', 'light', 'paper', 26, 'Watch this room come together', 'soul-lounge-1'),
    'armchair': (HOME / 'armchair-2.jpg', 'ink', 'dark', 'paper', 16, 'Our new chair, drawn by hand', 'funk-bounce-2'),
    'kitchen': (HOME / 'kitchen-1.jpg', 'ink', 'medium', 'paper', 30, 'Your dream kitchen, line by line', 'autumn-acoustic-1'),
    'guess-panda': (LIBRARY / 'animals-02-panda.jpg', 'ink', 'light', 'paper', 14, None, 'playful-curious-1'),
    'guess-van': (LIBRARY / 'travel-01-van.jpg', 'ink', 'medium', 'paper', 14, None, 'funk-bounce-1'),
    'guess-whale': (LIBRARY / 'animals-03-whale.jpg', 'ink', 'dark', 'paper', 14, None, 'playful-curious-1'),
    'guess-dunk': (SPORTS / 'dunk-1.jpg', 'ink', 'medium', 'paper', 14, None, 'funk-bounce-2'),
    'pumpkin': (LIBRARY / 'occasion-04-pumpkin.jpg', 'ink', 'medium', 'paper', 16, None, 'playful-spooky-1'),
}


def font(size, weight=750):
    f = ImageFont.truetype(str(FONT), size)
    try:
        f.set_variation_by_axes([weight])
    except (OSError, AttributeError):
        pass
    return f


def wrap(draw, text, f, width):
    lines, line = [], ''
    for word in text.split():
        test = f'{line} {word}'.strip()
        if draw.textlength(test, font=f) <= width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + [line]


def frame_at(video, seconds, path):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(seconds), '-i', str(video), '-frames:v', '1', '-q:v', '2', str(path)], check=True)
    return Image.open(path).convert('RGB')


def duration(path):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                                capture_output=True, text=True, check=True).stdout)


def cover_card(finished, title):
    """The first frame: the finished picture with the title on top, or a '?' card that hides the answer."""
    w, h = finished.size
    if title is None:
        card = finished.filter(ImageFilter.GaussianBlur(60)).point(lambda v: int(v * .35 + 255 * .65))
        d = ImageDraw.Draw(card)
        big = font(560, 850)
        d.text((w / 2, h * .44), '?', font=big, fill=BERRY, anchor='mm')
        f = font(78, 800)
        for i, line in enumerate(['Guess what', "we're drawing"]):
            d.text((w / 2, h * .70 + i * 96), line, font=f, fill=INK, anchor='mm')
        return card
    card = finished.copy()
    d = ImageDraw.Draw(card)
    f = font(76, 800)
    lines = wrap(d, title, f, w - 160)
    box_h = len(lines) * 92 + 70
    # Put the title just below the drawing (never on it), inside the 4:5 area the profile grid shows (y 285-1635).
    gray = finished.convert('L')
    background = gray.getpixel((8, h // 2))
    rows = [y for y in range(0, h, 4) if any(abs(gray.getpixel((x, y)) - background) > 28 for x in range(40, w - 40, 12))]
    bottom = max(rows) if rows else int(h * .7)
    top = min(bottom + 40, 1635 - box_h - 70)
    d.rounded_rectangle((60, top, w - 60, top + box_h), radius=36, fill=(255, 253, 248), outline=(239, 226, 202), width=3)
    for i, line in enumerate(lines):
        d.text((w / 2, top + 35 + 46 + i * 92), line, font=f, fill=INK, anchor='mm')
    small = font(40, 650)
    d.text((w / 2, top + box_h + 50), 'drawn with strokeberry.com', font=small, fill=BERRY, anchor='mm')
    return card


def build_reel(post_id):
    source, style, hand, canvas, seconds, title, track = PLAN[post_id]
    folder = OUT / post_id
    folder.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp())
    drawn = make(post_id, source, style, hand, canvas, seconds, work)            # 1080x1920 with end card, silent
    total = duration(drawn)
    finished = frame_at(drawn, max(0, total - (2.65 if isinstance(seconds, list) else 3.1)), work / 'finished.jpg')
    cover = cover_card(finished, title)
    cover.save(folder / 'cover.jpg', quality=92)
    still = work / 'still.mp4'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-loop', '1', '-t', str(COVER_SECONDS), '-i', str(folder / 'cover.jpg'),
                    '-r', '24', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', str(still)], check=True)
    joined = work / 'joined.mp4'
    (work / 'list.txt').write_text(f"file '{still}'\nfile '{drawn}'\n")
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(work / 'list.txt'),
                    '-c:v', 'libx264', '-crf', '20', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-r', '24', str(joined)], check=True)
    length = duration(joined)
    music = MUSIC / f'{track}.mp3'
    # Loop the track if the video is longer than it, fade in briefly and out over the end card.
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', str(joined), '-stream_loop', '-1', '-i', str(music),
                    '-filter_complex', f'[1:a]atrim=0:{length:.2f},afade=t=in:d=0.3,afade=t=out:st={length - 2:.2f}:d=2,volume=0.9[a]',
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest',
                    '-movflags', '+faststart', str(folder / 'reel.mp4')], check=True)
    for stage, at in (('lines', .45), ('color', .8)):   # stills for carousels
        frame_at(drawn, total * at if not isinstance(seconds, list) else total * at, folder / f'{stage}.jpg')
    finished.save(folder / 'finished.jpg', quality=92)
    shutil.rmtree(work, ignore_errors=True)
    return folder / 'reel.mp4'


def slide(image=None, headline='', body='', step=None, cta=False):
    w, h = 1080, 1350
    s = Image.new('RGB', (w, h), CREAM)
    d = ImageDraw.Draw(s)
    y = 90
    if step:
        f = font(34, 750)
        tw = d.textlength(step, font=f) + 48
        d.rounded_rectangle(((w - tw) / 2, y, (w + tw) / 2, y + 60), radius=30, fill=INK)
        d.text((w / 2, y + 30), step, font=f, fill=(255, 255, 255), anchor='mm')
        y += 100
    if headline:
        f = font(68 if len(headline) < 40 else 58, 820)
        for line in wrap(d, headline, f, w - 140):
            d.text((w / 2, y + 40), line, font=f, fill=INK, anchor='mm')
            y += 80
    if body:
        f = font(36, 500)
        for line in wrap(d, body, f, w - 180):
            d.text((w / 2, y + 30), line, font=f, fill=(95, 92, 88), anchor='mm')
            y += 48
    if image is not None:
        box = (100, y + 40, w - 100, h - 140)
        img = image.copy()
        # crop to the drawing itself (the 9:16 frame has paper above and below)
        img = img.crop((0, int(img.height * .2), img.width, int(img.height * .8))) if img.height > img.width * 1.3 else img
        img.thumbnail((box[2] - box[0], box[3] - box[1]))
        x0 = (w - img.width) // 2
        y0 = box[1] + (box[3] - box[1] - img.height) // 2
        d.rounded_rectangle((x0 - 14, y0 - 14, x0 + img.width + 14, y0 + img.height + 14), radius=30, fill=(255, 255, 255), outline=(239, 226, 202), width=3)
        s.paste(img, (x0, y0))
    if cta:
        m = Image.open(MASCOT).convert('RGBA')
        m.thumbnail((420, 420))
        s.paste(m, ((w - m.width) // 2, h - m.height - 260), m)
        f = font(44, 800)
        d.rounded_rectangle((240, h - 220, w - 240, h - 130), radius=45, fill=BERRY)
        d.text((w / 2, h - 175), 'strokeberry.com', font=f, fill=(255, 255, 255), anchor='mm')
    d.text((w - 60, h - 50), 'strokeberry', font=font(30, 800), fill=(180, 170, 155), anchor='rm')
    return s


# id: reel it draws from, then the words on each slide
CAROUSELS = {
    'process-skincare': ('skincare', 'From flat image to hand-drawn video', 'Swipe to see one product picture come to life',
                         'Any brand can make one. 3 free videos a month, no card.'),
    'process-living-room': ('living-room', 'How a room sketch becomes a video', 'Interior designers: swipe for the steps',
                            'Show clients their room being drawn. Free to try.'),
    'process-cafe': ('cafe', 'Your café logo, drawn in chalk', 'Swipe: from logo to chalkboard video',
                     'Cafés and bakeries: make your menu move. Free to try.'),
    'process-house': ('house', 'A listing post nobody else has', 'Realtors: swipe to see a home sketch come to life',
                      'Video packs from $5 for 5 videos. They never expire.'),
    'process-armchair': ('armchair', 'Launch your next piece like this', 'Furniture brands: swipe for the 4 steps',
                         'Videos made with Pro or a pack can be used in ads.'),
    'process-owl-lesson': ('owl-lesson', 'Turn a drawing sheet into a lesson', 'Teachers: swipe to see tutorial mode',
                           'Lessons up to 5 minutes with Pro. 3 free videos a month.'),
    'process-creator': ('creator', 'Upgrade your channel intro', 'Creators: swipe to see how it works',
                        'Export in 9:16 for Shorts, TikTok and Reels. Free to try.'),
}


def build_carousel(post_id):
    reel_id, hook, sub, closing = CAROUSELS[post_id]
    source = PLAN[reel_id][0]
    src_folder = OUT / reel_id
    if not (src_folder / 'finished.jpg').exists():
        build_reel(reel_id)
    folder = OUT / post_id
    folder.mkdir(parents=True, exist_ok=True)
    original = Image.open(source).convert('RGB')
    slides = [
        slide(Image.open(src_folder / 'finished.jpg'), hook, sub),
        slide(original, 'Upload any picture', 'A logo, a product, a sketch or a lesson sheet', step='Step 1'),
        slide(Image.open(src_folder / 'lines.jpg'), 'It draws the lines first', 'Big shapes, then details, like a real artist', step='Step 2'),
        slide(Image.open(src_folder / 'color.jpg'), 'Then paints the color in', 'With a realistic hand, in ink or pencil', step='Step 3'),
        slide(None, 'Download your video', closing, step='Step 4', cta=True),
    ]
    for i, s in enumerate(slides, 1):
        s.save(folder / f'slide-{i}.jpg', quality=92)
    return folder


if __name__ == '__main__':
    kind, ids = sys.argv[1], sys.argv[2:]
    for post_id in ids:
        print(post_id, '->', build_reel(post_id) if kind == 'reel' else build_carousel(post_id), flush=True)
