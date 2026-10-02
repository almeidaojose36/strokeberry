"""Render the 16:9 clips that play behind the landing-page hero (one at a time, sliding from one to the next).

    .venv/bin/python scripts/gallery/render_hero.py [output_dir]

Writes frontend/public/hero/<key>.mp4 and <key>.jpg (a frame with the finished colour, used as the poster). Each clip
is drawn on paper as a 720x720 square and placed on the right of a 1280x720 frame, so the hero's headline sits on plain
paper on the left and never covers the drawing. About 10 seconds each, realistic hand, no watermark or end card.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.pipeline import prepare_image, render  # noqa: E402

SRC = ROOT / 'assets' / 'hero-src'  # made by scripts/gallery/generate-hero-art.mjs; one subject per audience
CLIPS = [  # key, source image, style, hand
    ('skincare', 'skincare-2.jpg', 'ink', 'light'),     # e-commerce
    ('fashion', 'fashion-1.jpg', 'ink', 'dark'),        # fashion brands
    ('creator', 'creator-1.jpg', 'ink', 'medium'),      # YouTubers and creators
    ('cafe', 'cafe-2.jpg', 'ink', 'light'),             # cafés and food brands
    ('lesson', 'lesson-2.jpg', 'ink', 'dark'),          # teachers
    ('house', 'house-2.jpg', 'ink', 'medium'),          # real estate and local business
]
LEAD_IN = .4
BOARD = '0xfaf9f6'  # the paper colour (backend/pipeline.py PAPER), so the padding is seamless


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'frontend' / 'public' / 'hero'
    out.mkdir(parents=True, exist_ok=True)
    for key, image, style, hand in CLIPS:
        work = Path(tempfile.mkdtemp())
        prepare_image(SRC / image, work)
        settings = {'style': style, 'duration': 10, 'ratio': '1:1', 'resolution': '720p', 'color': True, 'pen': True,
                    'hand': hand, 'canvas': 'paper'}
        render(work, settings, lambda *a: None, work / 'raw.mp4')
        video = out / f'{key}.mp4'
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(LEAD_IN), '-i', str(work / 'raw.mp4'),
                        '-vf', f'pad=1280:720:{1280 - 720}:0:color={BOARD}', '-c:v', 'libx264',
                        '-crf', '27', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', str(video)], check=True)
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-sseof', '-1.2', '-i', str(video), '-frames:v', '1', '-q:v', '4',
                        str(out / f'{key}.jpg')], check=True)
        shutil.rmtree(work, ignore_errors=True)
        print(f'{key}: {video.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
