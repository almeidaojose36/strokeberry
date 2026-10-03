"""Render a batch of vertical (9:16, 1080x1920) showcase clips for TikTok, Reels and Shorts.

    .venv/bin/python scripts/social/render_showcase.py [output_dir] [keys...]

Original artwork only (our audience illustrations, the example library and tutorial sheets), never famous characters.
Each clip is drawn like a Pro export (no watermark) and ends on the "Made with Strokeberry" card, so every post carries
the address. Silent on purpose: sound is added on the platform. Default output: marketing/showcase/batch-01/.
Captions, hooks and tracking links for the batch live in CAPTIONS.md next to the videos.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app import DrawingStage, StepConfig  # noqa: E402
from backend.pipeline import prepare_image, render  # noqa: E402
from backend.steps import detect_panels, fallback_layout, four_step_reading_order, prepare_steps  # noqa: E402

HERO, LIBRARY, HOME = ROOT / 'assets' / 'hero-src', ROOT / 'frontend' / 'public' / 'library', ROOT / 'assets' / 'interiors-src'
LEAD_IN = .3
TUTORIAL = ['Guide shapes', 'Outlines', 'Details', 'Colour']
CLIPS = [  # number-key, source, style, hand, canvas, seconds (or tutorial step seconds)
    ('01-skincare', HERO / 'skincare-1.jpg', 'ink', 'light', 'paper', 12),
    ('02-fashion', HERO / 'fashion-2.jpg', 'ink', 'dark', 'paper', 12),
    ('03-cafe-chalkboard', HERO / 'cafe-1.jpg', 'ink', 'medium', 'greenboard', 12),
    ('04-classroom-blackboard', HERO / 'lesson-1.jpg', 'ink', 'dark', 'blackboard', 12),
    ('05-owl-lesson', LIBRARY / 'tutorial-00-owl.jpg', 'ink', 'light', 'paper', [3, 4, 4, 5]),
    ('06-dinosaur-lesson', LIBRARY / 'tutorial-02-dinosaur.jpg', 'ink', 'medium', 'paper', [3, 4, 4, 5]),
    ('07-house-sketch', HERO / 'house-1.jpg', 'ink', 'medium', 'paper', 12),
    ('08-just-listed', HERO / 'house-2.jpg', 'ink', 'light', 'paper', 12),
    ('09-creator-intro', HERO / 'creator-2.jpg', 'ink', 'dark', 'paper', 12),
    ('10-guess-panda', LIBRARY / 'animals-02-panda.jpg', 'ink', 'light', 'paper', 14),
    ('11-guess-van', LIBRARY / 'travel-01-van.jpg', 'ink', 'medium', 'paper', 14),
    ('12-guess-whale', LIBRARY / 'animals-03-whale.jpg', 'ink', 'dark', 'paper', 14),
    ('13-living-room', HOME / 'livingroom-2.jpg', 'ink', 'light', 'paper', 12),
    ('14-armchair', HOME / 'armchair-2.jpg', 'ink', 'dark', 'paper', 10),
    ('15-kitchen', HOME / 'kitchen-1.jpg', 'ink', 'medium', 'paper', 14),
]


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', *args], check=True)


def make(key, source, style, hand, canvas, seconds, out):
    work = Path(tempfile.mkdtemp())
    parent = work / 'source'
    parent.mkdir()
    prepare_image(source, parent)
    folder, duration = parent, seconds
    if isinstance(seconds, list):  # tutorial mode: the sheet's four panels become four stages
        layout = detect_panels(parent)
        if not layout['detected'] or len(layout['crops']) != 4:
            layout = fallback_layout(layout['width'], layout['height'], 2, 2)
        stages = [DrawingStage(crop=c, label=l, seconds=s) for c, l, s in zip(layout['crops'], TUTORIAL, seconds)]
        config = StepConfig(stages=stages, align=True).model_dump()
        config['stages'] = four_step_reading_order(config['stages'])
        folder = work / 'steps'
        folder.mkdir()
        duration = prepare_steps(parent, folder, config)['duration']
    settings = {'style': style, 'duration': duration, 'ratio': '9:16', 'resolution': '1080p', 'color': True, 'pen': True,
                'hand': hand, 'canvas': canvas, 'watermark': False, 'end_card': True}
    raw = work / 'raw.mp4'
    render(folder, settings, lambda *a: None, raw)
    video = out / f'{key}.mp4'
    ffmpeg('-ss', str(LEAD_IN), '-i', str(raw), '-c:v', 'libx264', '-crf', '20', '-preset', 'slow', '-pix_fmt', 'yuv420p',
           '-an', '-movflags', '+faststart', str(video))
    # Cover image: the finished drawing just before the end card (tutorials keep drawing until later, so later still).
    ffmpeg('-sseof', '-2.65' if isinstance(seconds, list) else '-3.2', '-i', str(video), '-frames:v', '1', '-q:v', '3', str(out / f'{key}-cover.jpg'))
    shutil.rmtree(work, ignore_errors=True)
    return video


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'marketing' / 'showcase' / 'batch-01'
    wanted = sys.argv[2:]
    out.mkdir(parents=True, exist_ok=True)
    for clip in CLIPS:
        if wanted and clip[0] not in wanted:
            continue
        print(f'-> {clip[0]} ...', end=' ', flush=True)
        video = make(*clip, out)
        print(f'{video.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
