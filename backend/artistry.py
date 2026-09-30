"""Deterministic stroke cleanup and a renderer-independent drawing timeline."""
import math

import cv2
import numpy as np

SCENE_VERSION = 4  # 4: strokes are ordered like a person draws (big shapes first); 3: white backgrounds blend into the paper


def resample(points, step=3.0):
    """Bound segment size without moving corners or endpoints."""
    result = [np.asarray(points[0], dtype=float)]
    for a, b in zip(points, points[1:]):
        a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        count = max(1, math.ceil(float(np.linalg.norm(b - a)) / step))
        for i in range(1, count + 1):
            point = a + (b - a) * (i / count)
            if np.linalg.norm(point - result[-1]) > 1e-6:
                result.append(point)
    return np.array(result)


def smooth_path(points):
    """One corner-cutting pass; keep sharp corners and open endpoints intact."""
    points = np.asarray(points, dtype=float)
    result = [points[0]]
    for i in range(1, len(points) - 1):
        a, b, c = points[i - 1:i + 2]
        u, v = b - a, c - b
        cosine = float(np.dot(u, v) / max(1e-9, np.linalg.norm(u) * np.linalg.norm(v)))
        if cosine < .45:
            result.append(b)
        else:
            # Limit displacement to one pixel to avoid shrinking recognizable details.
            result.extend([b - u * min(.2, 1 / max(1, np.linalg.norm(u))),
                           b + v * min(.2, 1 / max(1, np.linalg.norm(v)))])
    result.append(points[-1])
    return resample(result)


def clean_paths(contours, shape):
    """Suppress near-identical edge loops, while keeping separate nearby detail."""
    covered = np.zeros(shape, np.uint8)
    accepted = []
    for contour in contours[:1600]:
        if cv2.arcLength(contour, True) < 12:
            continue
        points = cv2.approxPolyDP(contour, .65, True).reshape(-1, 2)
        if len(points) < 2:
            continue
        points = np.vstack([points, points[0]])
        samples = resample(points, 1.5).round().astype(int)
        if np.mean(covered[samples[:, 1], samples[:, 0]] > 0) > .9:
            continue
        accepted.append(smooth_path(points))
        cv2.polylines(covered, [points.astype(np.int32)], False, 255, 3)
    return accepted


def make_timeline(paths):
    """Normalized events shared verbatim by the browser and MP4 renderers.

    Drawing takes 88% of the line-work phase and travel takes 12%. Curves and
    stroke endpoints receive extra time. Gaps never draw connecting marks.
    """
    events, previous = [], None
    for stroke, path in enumerate(paths):
        points = np.asarray(path, dtype=float)
        if len(points) < 2:
            continue
        lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
        total = float(lengths.sum())
        if total <= 1e-6:
            continue
        if previous is not None:
            distance = math.dist(previous, points[0])
            events.append({'kind': 'lift', 'a': list(previous), 'b': points[0].tolist(),
                           'cost': 12 + min(70, math.sqrt(distance) * 4), 'pressure': 0})
        travelled = 0
        for i, length in enumerate(lengths):
            if length <= 1e-6:
                continue
            t = (travelled + float(length) / 2) / total
            envelope = math.sin(math.pi * t) ** .55
            pressure = max(.3, min(1, .38 + .52 * envelope + .07 * math.sin(t * 19 + stroke * 1.7)))
            bend = 0
            if i and lengths[i - 1] > 1e-6:
                u, v = points[i] - points[i - 1], points[i + 1] - points[i]
                bend = (1 - float(np.clip(np.dot(u, v) / (lengths[i - 1] * length), -1, 1))) / 2
            cost = float(length) * (1 + 1.8 * bend + .65 * (1 - envelope))
            events.append({'kind': 'draw', 'a': points[i].tolist(), 'b': points[i + 1].tolist(),
                           'cost': cost, 'pressure': round(pressure, 4)})
            travelled += float(length)
        previous = points[-1]
    drawing = sum(e['cost'] for e in events if e['kind'] == 'draw')
    lifting = sum(e['cost'] for e in events if e['kind'] == 'lift')
    cursor = 0.0
    for event in events:
        budget = (.12 if event['kind'] == 'lift' else .88) if lifting else 1
        total = lifting if event['kind'] == 'lift' else drawing
        event['start'] = cursor
        cursor += event.pop('cost') / total * budget
        event['end'] = cursor
    if events:
        events[-1]['end'] = 1.0
    return events


def event_position(event, fraction):
    """Pause briefly, then arc above the paper during a pen lift."""
    fraction = max(0, min(1, fraction))
    lift = 0
    if event['kind'] == 'lift':
        t = max(0, min(1, (fraction - .15) / .7))
        fraction = t * t * (3 - 2 * t)
        lift = math.sin(math.pi * fraction)
    point = [event['a'][k] + (event['b'][k] - event['a'][k]) * fraction for k in range(2)]
    return point, lift


# ------------------------------------------------------------------------------ timing

def phase_bounds(duration, color):
    """(line_end, reveal): the line-work ends at line_end (a fraction of the video), then the colour takes `reveal` of it.

    The finished picture is held for a couple of seconds at most, so a 5-minute video doesn't sit on a still image for
    24 seconds while the clock keeps running. Short videos keep the classic 8% hold (65% drawing, 27% colour reveal)."""
    hold = min(.08, 2.0 / max(1, duration))
    reveal = .27 if color else 0
    return 1 - hold - reveal, reveal


def stage_hold(stage_seconds):
    """Fraction of one step-by-step stage spent holding its finished drawing (10%, but never more than ~1.5 s)."""
    return min(.1, 1.5 / max(.1, stage_seconds))


# ------------------------------------------------------------------------------ drawing order

TIER_BANDS = (.20, .16, .10)  # how far down the picture the pen may reach for its next stroke, per tier (fraction of height)


def stroke_tier(points, drawing_diagonal):
    """0 = major shapes, 1 = medium details, 2 = thin lines and tiny marks. Sizes are relative to the whole drawing.

    Size decides the tier. A long, straight line (a guitar string, a whisker) is a detail however long it is, so it is moved
    to the last tier: people draw the structure first and add those at the end."""
    points = np.asarray(points, np.float32)
    span = float(np.hypot(*(points.max(axis=0) - points.min(axis=0)))) / drawing_diagonal
    hull = cv2.convexHull(points.reshape(-1, 1, 2))
    hull_length = max(1e-6, float(cv2.arcLength(hull, True)))
    # How much room the stroke takes up around itself: ~0 for a straight line, higher for a curving outline or a closed shape.
    curviness = 4 * math.pi * float(cv2.contourArea(hull)) / (hull_length * hull_length)
    if curviness < .06 and span >= .12:
        return 2
    return 0 if span >= .30 else 1 if span >= .10 else 2


def start_at(points, pen):
    """Rotate a closed stroke so it begins at the vertex nearest to the pen, which keeps pen travel short."""
    body = np.asarray(points, float)[:-1]
    index = int(np.argmin(((body - pen) ** 2).sum(axis=1)))
    return np.vstack([np.roll(body, -index, axis=0), body[index]])


def order_strokes(paths, width, height):
    """Order strokes the way a person builds a drawing.

    1. Major shapes first, then medium details, then thin lines and tiny marks (coarse to fine).
    2. Within each group work from the top of the picture downwards; the next stroke is the nearest one inside a moving
       band, so the pen doesn't leap across the page.
    3. Every closed stroke starts where the pen already is."""
    if not len(paths):
        return []
    everything = np.vstack([np.asarray(p, float) for p in paths])
    diagonal = max(1.0, float(np.hypot(*(everything.max(axis=0) - everything.min(axis=0)))))  # the drawing, not the canvas
    tiers = {0: [], 1: [], 2: []}
    for path in paths:
        points = np.asarray(path, float)
        tiers[stroke_tier(points, diagonal)].append(points)
    ordered, pen = [], np.array([width / 2, 0.0])
    for tier in (0, 1, 2):
        pool = sorted(tiers[tier], key=lambda p: float(p[:, 1].min()))
        band = TIER_BANDS[tier] * height
        while pool:
            reach = float(pool[0][:, 1].min()) + band
            candidates = [k for k, p in enumerate(pool) if float(p[:, 1].min()) <= reach]
            best = min(candidates, key=lambda k: float(((pool[k] - pen) ** 2).sum(axis=1).min()))
            stroke = start_at(pool.pop(best), pen)
            ordered.append(stroke)
            pen = stroke[-1]
    return ordered
