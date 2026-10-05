"""Render the same picture twice, with the current stroke order and the experimental human-like one, and put them side by side.

    .venv/bin/python scripts/dev/compare_videos.py out.mp4 picture.jpg [more.jpg ...]

Left: current order. Right: experimental order (backend.artistry.order_strokes_human). Ink style, the pen hand, 16 seconds each (the new order gives the colour 38% of the time instead of 27%).
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.artistry import make_timeline, order_strokes_human, silhouette_mask  # noqa: E402
from PIL import Image  # noqa: E402
from backend.inkfill import inside_share, ink_masks, outline_strokes  # noqa: E402
from backend.paintorder import region_ranks  # noqa: E402
from backend.pipeline import BRUSH_DEPTH, PAPER, brush_texture, paint_path, prepare_image, render  # noqa: E402

SETTINGS = {'style': 'ink', 'duration': 16, 'ratio': '1:1', 'resolution': '720p', 'color': True, 'pen': True, 'hand': 'medium', 'canvas': 'paper'}
FONT = '/System/Library/Fonts/Helvetica.ttc'


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out, pictures = Path(args[0]), args[1:]
    clips = []
    work = Path(tempfile.mkdtemp())
    for n, picture in enumerate(pictures):
        old, new = work / f'{n}-old', work / f'{n}-new'
        old.mkdir()
        scene = prepare_image(Path(picture), old)
        shutil.copytree(old, new)
        image = Image.open(new / 'source.png').convert('RGB')
        rgb = np.array(image)
        distance = np.abs(rgb.astype(np.float32) - np.array(PAPER, np.float32)).sum(axis=2)
        _, thick = ink_masks(rgb, distance, scene.get('line_width'))
        outlines = outline_strokes(thick)                       # the pen draws the full silhouette of hair, boots, soles...
        solid = cv2.dilate(thick.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        kept = [np.asarray(p, float) for p in scene['paths'] if inside_share(p, solid) < .7]   # ...instead of a centre line through them
        outer = silhouette_mask(distance >= 14)
        human = [p.tolist() for p in order_strokes_human(kept + outlines, scene['width'], scene['height'], (), outer)]
        changed = dict(scene, paths=human, timeline=make_timeline(human, human_pace=True), strokes=len(human), reveal_edge=3, reveal_share=.38, natural_hand=True)
        ranks = region_ranks(rgb, distance, brush_texture(distance.shape), BRUSH_DEPTH, scene.get('line_width'))
        Image.fromarray(np.uint8(ranks * 245)).save(new / 'reveal.png')
        changed['paint_path'] = paint_path(np.uint8(ranks * 245), distance > 30, samples=360, tolerance=2, reach_share=.025, offset=3)
        (new / 'scene.json').write_text(json.dumps(changed))
        lifts = lambda s: sum(1 for e in s['timeline'] if e['kind'] == 'lift')
        print(f'{Path(picture).name}: strokes {scene["strokes"]} -> {len(human)}, pen lifts {lifts(scene)} -> {lifts(changed)}')
        for folder, label in ((old, 'current order'), (new, 'new order')):
            video = work / f'{folder.name}.mp4'
            render(folder, dict(SETTINGS), lambda *a: None, video)
            labelled = work / f'{folder.name}-labelled.mp4'
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', str(video), '-vf',
                            f"drawtext=fontfile={FONT}:text='{label}':x=16:y=14:fontsize=30:fontcolor=black:box=1:boxcolor=white@0.8:boxborderw=8",
                            '-an', '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', str(labelled)], check=True)
        pair = work / f'{n}-pair.mp4'
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', str(work / f'{n}-old-labelled.mp4'), '-i', str(work / f'{n}-new-labelled.mp4'),
                        '-filter_complex', 'hstack=inputs=2', '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(pair)], check=True)
        clips.append(pair)
    listing = work / 'list.txt'
    listing.write_text(''.join(f"file '{c}'\n" for c in clips))
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing), '-c', 'copy', str(out)], check=True)
    shutil.rmtree(work, ignore_errors=True)
    print(out)


main()
