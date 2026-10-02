"""Render the landing-page gallery videos with the current drawing engine.

    .venv/bin/python scripts/gallery/render_gallery.py [output_dir] [keys...]

Reads the source illustrations in assets/gallery-src/ and writes <key>.mp4 (square, 720p) plus a finished-frame
<key>.jpg poster for each. No accounts or database are involved. The default output is frontend/public/gallery/;
pass another folder to review the clips before replacing the live ones. Needs ffmpeg.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app import DrawingStage, StepConfig  # noqa: E402
from backend.pipeline import prepare_image, render  # noqa: E402
from backend.steps import detect_panels, four_step_reading_order, prepare_steps  # noqa: E402

SRC = ROOT / 'assets' / 'gallery-src'
LEAD_IN = 0.5  # seconds of empty canvas trimmed from the start so a card is never blank when it appears
ITEMS = [
    {'key': 'cat', 'style': 'pencil', 'duration': 10, 'hand': 'light'},
    {'key': 'sneaker', 'style': 'ink', 'duration': 10, 'hand': 'medium'},
    {'key': 'coffee', 'style': 'ink', 'duration': 10},
    {'key': 'wreath', 'style': 'pencil', 'duration': 12},
    {'key': 'balloon', 'style': 'ink', 'duration': 10, 'hand': 'dark'},
    {'key': 'puppy', 'style': 'ink', 'duration': 12, 'hand': 'light'},
    {'key': 'fox', 'style': 'ink', 'duration': 12, 'hand': 'dark', 'canvas': 'greenboard'},
    # one per audience (the same art as the hero clips, square for the gallery)
    {'key': 'skincare', 'style': 'ink', 'duration': 12, 'hand': 'light'},
    {'key': 'fashion', 'style': 'ink', 'duration': 12, 'hand': 'dark'},
    {'key': 'creator', 'style': 'ink', 'duration': 12, 'hand': 'medium'},
    {'key': 'cafe', 'style': 'ink', 'duration': 12, 'hand': 'light'},
    {'key': 'lesson', 'style': 'ink', 'duration': 12, 'hand': 'dark'},
    {'key': 'house', 'style': 'ink', 'duration': 12, 'hand': 'medium'},
    {'key': 'strawberry', 'steps': ['Body shape', 'Leaves & headphones', 'Face & details', 'Color'], 'seconds': [3, 4, 5, 4],
     # Crops sit just inside the light-blue dividers of the source sheet (960 px square).
     'crops': [{'x': x / 960, 'y': y / 960, 'width': 472 / 960, 'height': 472 / 960} for x, y in ((0, 0), (486, 0), (0, 486), (486, 486))]},
    {'key': 'owl', 'steps': ['Guide shapes', 'Outlines', 'Details', 'Color'], 'seconds': [3, 4, 4, 5]},
]


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', *args], check=True)


def make_video(item, manifest, out_dir):
    work = Path(tempfile.mkdtemp())
    parent = work / 'source'
    parent.mkdir()
    prepare_image(SRC / manifest[item['key']], parent)
    folder, duration = parent, item.get('duration')
    if item.get('steps'):
        crops = item.get('crops')
        if not crops:
            layout = detect_panels(parent)
            if not layout['detected'] or len(layout['crops']) != len(item['steps']):
                raise RuntimeError(f"expected {len(item['steps'])} panels, found {len(layout['crops'])}")
            crops = layout['crops']
        stages = [DrawingStage(crop=crop, label=label, seconds=seconds) for crop, label, seconds in zip(crops, item['steps'], item['seconds'])]
        config = StepConfig(stages=stages, align=True).model_dump()
        config['stages'] = four_step_reading_order(config['stages'])
        folder = work / 'steps'
        folder.mkdir()
        scene = prepare_steps(parent, folder, config)
        duration = scene['duration']
    settings = {'style': item.get('style', 'pencil'), 'duration': duration, 'ratio': '1:1', 'resolution': '720p', 'color': True, 'pen': True,
                'hand': item.get('hand', 'pencil'), 'canvas': item.get('canvas', 'paper')}  # showcase clips are like Pro: no end card
    raw = work / 'raw.mp4'
    render(folder, settings, lambda *a: None, raw)
    video = out_dir / f"{item['key']}.mp4"
    ffmpeg('-ss', str(LEAD_IN), '-i', str(raw), '-c:v', 'libx264', '-crf', '22', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', str(video))
    ffmpeg('-sseof', '-0.2', '-i', str(video), '-frames:v', '1', '-q:v', '3', str(out_dir / f"{item['key']}.jpg"))
    shutil.rmtree(work, ignore_errors=True)
    return {'key': item['key'], 'style': 'steps' if item.get('steps') else settings['style'], 'duration': duration,
            'hand': settings['hand'], 'canvas': settings['canvas']}


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'frontend' / 'public' / 'gallery'
    wanted = sys.argv[2:]
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((SRC / 'manifest.json').read_text())
    results = []
    for item in ITEMS:
        if wanted and item['key'] not in wanted:
            continue
        print(f"-> {item['key']} ...", end=' ', flush=True)
        results.append(make_video(item, manifest, out_dir))
        print('done')
    (out_dir / 'gallery.json').write_text(json.dumps(results, indent=2) + '\n')
    print(f'{len(results)} videos written to {out_dir}')


if __name__ == '__main__':
    main()
