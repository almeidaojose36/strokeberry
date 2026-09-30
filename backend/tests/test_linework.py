import numpy as np
import cv2
import pytest

from backend import linework


def drawing(fill=False):
    """A white page with a thick black circle outline (and optionally a big black blob and a small one)."""
    image = np.full((400, 400, 3), 255, np.uint8)
    cv2.circle(image, (200, 200), 140, (20, 20, 20), 8)
    cv2.line(image, (100, 60), (300, 340), (20, 20, 20), 6)
    cv2.circle(image, (330, 70), 5, (20, 20, 20), -1)
    if fill:
        cv2.circle(image, (110, 300), 32, (20, 20, 20), -1)   # a big black blob (like a pupil): to be painted, not lined
    cv2.circle(image, (200, 200), 60, (236, 45, 52), -1)
    return image


def length(stroke):
    return float(np.linalg.norm(np.diff(stroke, axis=0), axis=1).sum())


def test_each_outline_becomes_one_centre_line_not_two():
    result = linework.extract_strokes(drawing())
    assert result is not None
    strokes, width = result
    assert 6 <= width <= 12                                    # measured the line thickness (8 px)
    total = sum(length(s) for s in strokes)
    circle, diagonal = 2 * np.pi * 140, np.hypot(200, 280)
    assert 0.8 * (circle + diagonal) < total < 1.25 * (circle + diagonal)   # once each (thinning trims a little); edge tracing would be about double
    assert len(strokes) <= 8


def test_thick_black_areas_are_left_to_be_painted_not_drawn():
    strokes, _ = linework.extract_strokes(drawing(fill=True))
    blob = np.array([110, 300])
    assert not any(np.hypot(*(s - blob).T).min() < 20 for s in strokes)      # nothing traced inside the black blob


def test_pictures_without_black_outlines_fall_back_to_edge_tracing():
    rng = np.random.default_rng(3)
    soft = cv2.GaussianBlur(rng.integers(90, 255, (300, 300, 3), dtype=np.uint8), (0, 0), 10)   # pastel, no dark lines
    assert linework.extract_strokes(soft) is None
    strokes = linework.edge_strokes(drawing())                                # ...but edges still become single lines
    assert strokes and all(len(s) >= 2 for s in strokes)


def test_thinning_gives_a_one_pixel_line_and_tracing_follows_it_unbroken():
    canvas = np.zeros((60, 200), np.uint8)
    cv2.line(canvas, (10, 10), (190, 50), 255, 7)                             # a thick diagonal
    skeleton = linework.prune_redundant(linework.thin(canvas))
    paths = linework.trace(skeleton)
    assert len(paths) == 1                                                    # one unbroken stroke, not a string of fragments
    assert length(paths[0]) > 0.95 * np.hypot(180, 40)


def test_thick_dark_shapes_get_an_outline_too():
    strokes, _ = linework.extract_strokes(drawing(fill=True))
    drawn = np.zeros((400, 400), np.uint8)
    for stroke in strokes:
        cv2.polylines(drawn, [np.round(stroke).astype(np.int32)], False, 255, 1)
    ring = drawn[300 - 40:300 + 41, 110 - 40:110 + 41]
    assert ring.any(), 'the filled blob (a nose, say) was never outlined by the pen'
    assert not drawn[300 - 10:300 + 11, 110 - 10:110 + 11].any()   # ...but it is outlined, not scribbled over


def unlined_patch_drawing():
    image = np.full((400, 400, 3), 255, np.uint8)
    cv2.circle(image, (200, 200), 170, (20, 20, 20), 6)
    cv2.line(image, (60, 120), (340, 120), (20, 20, 20), 6)
    cv2.line(image, (60, 300), (340, 300), (20, 20, 20), 6)
    cv2.line(image, (200, 40), (200, 100), (20, 20, 20), 6)
    cv2.fillPoly(image, [np.array([[120, 160], [280, 170], [260, 260], [140, 250]])], (240, 140, 60))   # a colour patch with no outline
    return image


def test_a_colour_patch_without_an_outline_is_suggested_a_line():
    image = unlined_patch_drawing()
    strokes, width = linework.extract_strokes(image)
    suggested = linework.missing_lines(image, strokes, width)
    assert len(suggested) >= 1
    patch = np.array([200, 210])
    assert any(np.hypot(*(s - patch).T).min() < 90 for s in suggested)


def test_fully_outlined_art_gets_no_suggestions():
    image = drawing()
    strokes, width = linework.extract_strokes(image)
    assert linework.missing_lines(image, strokes, width) == []
