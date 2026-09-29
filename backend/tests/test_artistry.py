import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from backend.artistry import clean_paths, event_position, make_timeline, smooth_path
from backend.artistry import SCENE_VERSION
from backend.pipeline import PAPER, draw_mark, load_scene, prepare_image
from .test_pipeline import illustration


def test_duplicate_edges_removed_and_separate_details_kept():
    first = np.array([[10, 10], [60, 10], [60, 60], [10, 60]], np.int32).reshape(-1, 1, 2)
    detail = first + np.array([80, 0])
    paths = clean_paths([first, first[::-1], detail], (100, 180))
    assert len(paths) == 2
    # A right angle stays sharp; smoothing does not round off architecture.
    assert any(np.allclose(p, [60, 10]) for p in paths[0])


def test_smoothing_keeps_endpoints_and_bounds_displacement():
    points = np.array([[0, 0], [20, 3], [40, 0]], dtype=float)
    smooth = smooth_path(points)
    assert np.allclose(smooth[0], points[0])
    assert np.allclose(smooth[-1], points[-1])
    assert max(np.linalg.norm(np.diff(smooth, axis=0), axis=1)) <= 3.001
    assert min(np.linalg.norm(smooth - points[1], axis=1)) <= 1.01


def test_timeline_allocates_lifts_without_drawing_connectors():
    paths = [[[0, 0], [10, 0], [20, 0], [20, 10]], [[80, 80], [90, 80]]]
    events = make_timeline(paths)
    assert events == make_timeline(paths)
    assert events[0]['start'] == 0
    assert events[-1]['end'] == 1
    assert all(e['end'] > e['start'] for e in events)
    assert all(a['end'] == b['start'] for a, b in zip(events, events[1:]))
    lifts = [e for e in events if e['kind'] == 'lift']
    assert sum(e['end']-e['start'] for e in lifts) == pytest.approx(.12)
    point, height = event_position(lifts[0], .5)
    assert point == pytest.approx([50, 45])
    assert height == pytest.approx(1)
    assert event_position(lifts[0], .1)[0] == lifts[0]['a']
    assert make_timeline([]) == []


def test_curves_slow_down_and_pressure_varies():
    paths = [[[0, 0], [10, 0], [10, 10], [20, 10], [30, 10], [40, 10]]]
    events = make_timeline(paths)
    # Equal-length interior segments: corner gets more time than a straight.
    assert events[2]['end']-events[2]['start'] > events[3]['end']-events[3]['start']
    assert max(e['pressure'] for e in events) - min(e['pressure'] for e in events) > .1
    light = np.full((80, 100, 3), PAPER, np.uint8)
    heavy = light.copy()
    draw_mark(light, (10, 40), (90, 40), .3, 'pencil', 2)
    draw_mark(heavy, (10, 40), (90, 40), 1, 'pencil', 2)
    assert heavy.sum() < light.sum()
    assert np.count_nonzero(heavy[:, :, 0] < 240) > np.count_nonzero(light[:, :, 0] < 240)


def test_old_projects_upgrade_once_without_losing_exports(tmp_path):
    original = prepare_image(illustration(), tmp_path)
    original.pop('version')
    original.pop('timeline')
    (tmp_path / 'scene.json').write_text(json.dumps(original))
    export = tmp_path / 'previous.mp4'
    export.write_bytes(b'existing export')
    updated = load_scene(tmp_path)
    assert updated['version'] == SCENE_VERSION and updated['timeline']
    timestamp = (tmp_path / 'scene.json').stat().st_mtime_ns
    assert load_scene(tmp_path) == updated
    assert (tmp_path / 'scene.json').stat().st_mtime_ns == timestamp
    assert export.read_bytes() == b'existing export'


@pytest.mark.skipif(not shutil.which('node'), reason='Node required for cross-renderer verification')
def test_browser_and_encoder_have_identical_pen_positions():
    events = make_timeline([[[0, 0], [3, 8], [9, 10]], [[90, 50], [92, 60]]])
    samples = [{'event': event, 'fraction': f} for event in events for f in [0, .1, .3, .5, .9, 1]]
    code = """import {eventPosition} from './frontend/src/drawing.js';
    let data=''; for await(const chunk of process.stdin)data+=chunk;
    console.log(JSON.stringify(JSON.parse(data).map(s=>eventPosition(s.event,s.fraction))));"""
    result = subprocess.run(['node', '--input-type=module', '-e', code], input=json.dumps(samples),
                            text=True, capture_output=True, check=True, cwd=Path(__file__).resolve().parents[2])
    for sample, actual in zip(samples, json.loads(result.stdout)):
        point, lift = event_position(sample['event'], sample['fraction'])
        assert actual['point'] == pytest.approx(point)
        assert actual['lift'] == pytest.approx(lift)


def loop(cx, cy, w, h):
    """A closed rectangular stroke centred on (cx, cy)."""
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def thin_line(x, y0, y1):
    """The traced loop around a straight line, like a guitar string."""
    return [[x, y0], [x + 1, y0], [x + 1, y1], [x, y1], [x, y0]]


def test_strokes_are_ordered_big_shapes_first_then_details_then_thin_lines():
    from backend.artistry import order_strokes
    big = loop(200, 250, 300, 380)            # the silhouette
    medium = loop(200, 150, 90, 70)           # a feature
    tiny = [loop(120 + 20 * i, 300, 8, 8) for i in range(4)]  # sprinkles
    string = thin_line(200, 100, 400)         # a long straight line
    ordered = order_strokes([*tiny, string, medium, big], 400, 500)
    spans = [max(p[0] for p in s) - min(p[0] for p in s) + max(p[1] for p in s) - min(p[1] for p in s) for s in ordered]
    assert len(ordered) == 7
    assert spans[0] == 680                     # the silhouette (300 wide + 380 tall) is drawn first
    assert spans[1] == 160                     # then the medium feature (90 + 70)
    assert sorted(spans[2:]) == [16] * 4 + [301]  # the sprinkles and the long straight line are the final details


def test_strokes_of_the_same_size_go_from_the_top_of_the_picture_downwards():
    from backend.artistry import order_strokes
    rows = [loop(200, y, 120, 60) for y in (400, 100, 250, 550)]
    ordered = order_strokes(rows, 400, 700)
    tops = [min(p[1] for p in stroke) for stroke in ordered]
    assert tops == sorted(tops)


def test_each_stroke_begins_where_the_pen_already_is():
    from backend.artistry import order_strokes
    ordered = order_strokes([loop(100, 100, 100, 100), loop(300, 100, 100, 100)], 400, 300)
    first_end, second_start = ordered[0][-1], ordered[1][0]
    assert tuple(first_end) == tuple(ordered[0][0])                    # closed strokes finish where they began
    assert abs(second_start[0] - 250) < 1 and abs(second_start[1] - 50) < 60  # next one starts on its nearest side
    assert order_strokes([], 400, 300) == []


def test_ordering_keeps_every_stroke_intact():
    import numpy as np
    from backend.artistry import order_strokes
    strokes = [loop(100 + 40 * i, 60 + 70 * i, 50 + 10 * i, 30) for i in range(6)]
    ordered = order_strokes(strokes, 500, 500)
    key = lambda s: sorted(map(tuple, np.round(np.asarray(s)[:-1], 3)))
    assert sorted(map(key, ordered)) == sorted(map(key, strokes))
    assert all(tuple(s[0]) == tuple(s[-1]) for s in ordered)


def test_prepared_images_are_drawn_outline_first(tmp_path):
    import numpy as np
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (400, 400), 'white')
    draw = ImageDraw.Draw(image)
    draw.ellipse((60, 60, 340, 340), outline=(20, 20, 20), width=6, fill=(240, 200, 60))
    for x in (140, 200, 260):
        draw.ellipse((x - 10, 190, x + 10, 210), fill=(30, 30, 30))  # small marks inside
    folder = tmp_path / 'p'
    folder.mkdir()
    src = tmp_path / 'in.png'
    image.save(src)
    scene = prepare_image(src, folder)
    extent = lambda s: np.ptp(np.asarray(s)[:, 0]) + np.ptp(np.asarray(s)[:, 1])
    assert extent(scene['paths'][0]) > 3 * extent(scene['paths'][-1])
