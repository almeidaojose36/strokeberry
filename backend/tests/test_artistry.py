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
