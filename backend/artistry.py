"""Deterministic stroke cleanup and a renderer-independent drawing timeline."""
import math

import cv2
import numpy as np

SCENE_VERSION = 12  # 6: only real black outlines are drawn, as single centre lines (edge tracing is the fallback); 5: the colour reveal is spread by visible weight; 4: strokes ordered like a person draws; 3: white backgrounds blend into the paper


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


def make_timeline(paths, human_pace=False, marker_from=None):
    """Normalized events shared verbatim by the browser and MP4 renderers.

    Drawing takes 88% of the line-work phase and travel takes 12%. Curves and
    stroke endpoints receive extra time. Gaps never draw connecting marks.
    """
    events, previous = [], None
    everything = [np.asarray(p, float) for p in paths if len(p) >= 2]
    extent = np.vstack(everything) if everything else np.zeros((2, 2))
    diagonal = max(1.0, float(np.hypot(*(extent.max(axis=0) - extent.min(axis=0)))))
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
        pace = 1.0
        if human_pace:   # slow on small details, quick on specks and along long straight lines
            chord = float(np.hypot(*(points[-1] - points[0])))
            pace = 1 + .9 * max(0.0, 1 - total / (.08 * diagonal))
            if total < .015 * diagonal:      # specks and tufts: tick them in quickly, don't plot each one as a deliberate stroke
                pace = .4
            if total > .15 * diagonal and chord / total > .97:
                pace = .75
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
            cost = float(length) * (1 + 1.8 * bend + .65 * (1 - envelope)) * pace
            event = {'kind': 'draw', 'a': points[i].tolist(), 'b': points[i + 1].tolist(), 'cost': cost, 'pressure': round(pressure, 4)}
            if marker_from is not None and stroke >= marker_from:   # filling a black shape in with a thick marker
                event.update(marker=True, pressure=.8)
            events.append(event)
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

def phase_bounds(duration, color, reveal_share=None):
    """(line_end, reveal): the line-work ends at line_end (a fraction of the video), then the colour takes `reveal` of it.

    The finished picture is held for a couple of seconds at most, so a 5-minute video doesn't sit on a still image for
    24 seconds while the clock keeps running. Short videos keep the classic 8% hold (65% drawing, 27% colour reveal)."""
    hold = min(.08, 2.0 / max(1, duration))
    reveal = (.27 if reveal_share is None else reveal_share) if color else 0
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


def is_closed(points):
    return len(points) > 3 and float(np.hypot(*(np.asarray(points[0], float) - np.asarray(points[-1], float)))) < 1e-6


def start_at(points, pen):
    """Begin a stroke where the pen already is: a closed stroke is rotated to its nearest vertex, an open one is drawn
    from whichever end is nearer."""
    points = np.asarray(points, float)
    if not is_closed(points):
        return points if np.hypot(*(points[0] - pen)) <= np.hypot(*(points[-1] - pen)) else points[::-1]
    body = points[:-1]
    index = int(np.argmin(((body - pen) ** 2).sum(axis=1)))
    return np.vstack([np.roll(body, -index, axis=0), body[index]])


def pen_distance(points, pen):
    """How far the pen must travel to start this stroke (its ends for an open stroke, any vertex for a closed one)."""
    points = np.asarray(points, float)
    reachable = points if is_closed(points) else points[[0, -1]]
    return float(((reachable - pen) ** 2).sum(axis=1).min())


def order_strokes(paths, width, height):
    """    Order strokes the way a person builds a drawing.

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
            best = min(candidates, key=lambda k: pen_distance(pool[k], pen))
            stroke = start_at(pool.pop(best), pen)
            ordered.append(stroke)
            pen = stroke[-1]
    return ordered


# ------------------------------------------------------------------------------ human-like drawing order
#
# People don't sweep a picture from big to small. They finish one part at a time (the head, then its face; the skirt, then
# its folds), build outward from what is already on the page, draw a matching pair (both arms, both legs, both eyes) one
# after the other, leave shading and texture for the end as a run of parallel lines, and move the pen in its natural
# direction (down and to the right, circles counter-clockwise).

PAIR_SIZE = (.72, 1.38)     # a stroke pairs with a mirror twin of about the same size
CONTINUE = .012            # a stroke that starts within this distance of the pen (share of the drawing) continues the contour
TEXTURE_LINK = .035        # texture marks closer than this (gap between their boxes) belong to the same patch
LEFT_BIAS = .12            # a right-handed artist works from the top left towards the bottom right, so the hand never covers fresh lines
AMBIGUOUS_START = .06       # when both ends of a line are about as near, begin at the natural one (top, or left)


def _area(points):
    return abs(float(cv2.contourArea(np.asarray(points, np.float32).reshape(-1, 1, 2))))


def _signed_area(points):
    x, y = np.asarray(points, float)[:, 0], np.asarray(points, float)[:, 1]
    return float(0.5 * np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]))


def _smoothness(points):
    """Length of the stroke divided by the perimeter of its convex hull: about 1 for a circle or a box, much more for jagged outlines."""
    points = np.asarray(points, np.float32)
    length = float(np.sum(np.hypot(*np.diff(points, axis=0).T)))
    return length / max(1e-6, float(cv2.arcLength(cv2.convexHull(points.reshape(-1, 1, 2)), True)))


def _bounds(points):
    return points.min(axis=0), points.max(axis=0)


def _parents(strokes):
    """For each stroke, the index of the smallest larger closed stroke that contains it (its 'part'), or None."""
    info = []
    for points in strokes:
        low, high = _bounds(points)
        info.append((low, high, _area(points) if is_closed(points) else 0.0, points.mean(axis=0)))
    parents = [None] * len(strokes)
    for i, (low, high, area, centre) in enumerate(info):
        best, best_area = None, float('inf')
        for j, (jlow, jhigh, jarea, _) in enumerate(info):
            if j == i or jarea <= area * 1.15 or jarea >= best_area:
                continue
            if not (jlow[0] <= centre[0] <= jhigh[0] and jlow[1] <= centre[1] <= jhigh[1]):
                continue
            if cv2.pointPolygonTest(strokes[j].astype(np.float32).reshape(-1, 1, 2), (float(centre[0]), float(centre[1])), False) >= 0:
                best, best_area = j, jarea
        parents[i] = best
    return parents


def _natural_start(points, pen, diagonal):
    """Which way to draw an open line: from the end nearer the pen, or, when the ends are about as near, from the top
    (for a mostly vertical line) or the left (for a mostly horizontal one)."""
    near_a, near_b = float(np.hypot(*(points[0] - pen))), float(np.hypot(*(points[-1] - pen)))
    if abs(near_a - near_b) > AMBIGUOUS_START * diagonal:
        return points if near_a <= near_b else points[::-1]
    span = points[-1] - points[0]
    key = 1 if abs(span[1]) >= abs(span[0]) else 0
    return points if points[0][key] <= points[-1][key] else points[::-1]


def _begin(points, pen, diagonal):
    points = np.asarray(points, float)
    if is_closed(points):
        if _signed_area(points) > 0:  # clockwise on screen: people draw loops counter-clockwise
            points = points[::-1]
        return start_at(points, pen)
    return _natural_start(points, pen, diagonal)


def _pick(pool, pen, band):
    """The next stroke of a group: nearest to the pen among those no further down than the top of the group plus a band."""
    reach = min(float(p[:, 1].min()) for p in pool) + band
    near = [k for k, p in enumerate(pool) if float(p[:, 1].min()) <= reach]
    return min(near, key=lambda k: math.sqrt(pen_distance(pool[k], pen)) + LEFT_BIAS * float(pool[k][:, 0].min()))


def _twin(chosen, pool, axis, diagonal):
    """A stroke in the pool that mirrors `chosen` across the picture's centre line (the other arm, leg, eye...), or None."""
    low, high = _bounds(chosen)
    centre, size = (low + high) / 2, max(1e-6, float(np.hypot(*(high - low))))
    best, best_gap = None, float('inf')
    for k, other in enumerate(pool):
        olow, ohigh = _bounds(other)
        ocentre, osize = (olow + ohigh) / 2, float(np.hypot(*(ohigh - olow)))
        if not PAIR_SIZE[0] <= osize / size <= PAIR_SIZE[1] or abs(ocentre[1] - centre[1]) > .05 * diagonal:
            continue
        gap = abs(centre[0] + ocentre[0] - 2 * axis)
        if gap < .06 * diagonal and abs(centre[0] - ocentre[0]) > .08 * diagonal and gap < best_gap:
            best, best_gap = k, gap
    return best


def _patches(strokes, diagonal):
    """Group marks into local patches (a mane, a patch of fur, a run of hatching): marks whose boxes nearly touch share a
    patch. Returns lists of indices, patches ordered from the top of the picture down."""
    boxes = [_bounds(p) for p in strokes]
    gap = TEXTURE_LINK * diagonal
    root = list(range(len(strokes)))

    def find(k):
        while root[k] != k:
            root[k] = root[root[k]]
            k = root[k]
        return k

    for i, (alow, ahigh) in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            blow, bhigh = boxes[j]
            if (blow[0] - ahigh[0] <= gap and alow[0] - bhigh[0] <= gap and blow[1] - ahigh[1] <= gap and alow[1] - bhigh[1] <= gap):
                root[find(i)] = find(j)
    patches = {}
    for k in range(len(strokes)):
        patches.setdefault(find(k), []).append(k)
    return sorted(patches.values(), key=lambda members: min(float(strokes[k][:, 1].min()) for k in members))


FRAME_SMOOTH = 1.12  # ...and smooth: its length is at most this times the length of the shape's convex hull (a wreath is far more jagged)
FRAME_SHARE = .55   # a closed ring at least this share of the drawing's width and height is a frame
JOIN_GAP = .015     # fragments whose ends are within this share of the drawing apart are joined into one line
JOIN_TURN = .5      # ...if the line carries on in roughly the same direction (cosine of the turn at the joint)


def _heading(points, end, count=4):
    """Unit direction in which the line leaves the given end ('start' or 'end'), measured over a few points."""
    a, b = (points[min(count, len(points) - 1)], points[0]) if end == 'start' else (points[-1 - min(count, len(points) - 1)], points[-1])
    v = b - a if end == 'end' else a - b      # outwards from the end
    return v / max(1e-9, float(np.hypot(*v)))


def join_fragments(paths, diagonal):
    """Join open lines that meet end to end (the tracer cuts one outline into several pieces) into longer lines, so a
    contour is drawn in one pass like a person would, with fewer pen lifts. Only joins that carry on in about the same direction
    are made, so a T-junction or a corner between separate shapes is left alone. When a chain of pieces comes back round to
    its own start (a circle, a ring), it is closed into one loop. Closed strokes are never touched.

    One pass: every pair of line ends within JOIN_GAP of each other is a candidate, taken nearest first."""
    lines = [np.asarray(p, float) for p in paths]
    gap = JOIN_GAP * diagonal
    open_ids = [i for i, p in enumerate(lines) if not is_closed(p) and len(p) >= 2]
    if len(open_ids) < 2:
        return lines
    ends = np.array([lines[i][0 if which == 0 else -1] for i in open_ids for which in (0, 1)])      # endpoint k = 2*j + which
    heads = np.array([_heading(lines[i], 'start' if which == 0 else 'end') for i in open_ids for which in (0, 1)])
    distance = np.hypot(*(ends[:, None, :] - ends[None, :, :]).transpose(2, 0, 1))
    first, second = np.nonzero(np.triu(distance <= gap, 1))
    linked, used = {}, set()
    for k in np.argsort(distance[first, second], kind='stable'):
        a_, b_ = int(first[k]), int(second[k])
        if a_ in used or b_ in used:
            continue
        same = a_ // 2 == b_ // 2
        if same and a_ // 2 >= 0 and float(np.sum(np.hypot(*np.diff(lines[open_ids[a_ // 2]], axis=0).T))) < 4 * gap:
            continue                                         # a tiny stroke is not turned into a loop
        if float(-heads[a_] @ heads[b_]) < JOIN_TURN:      # the two lines must head towards each other
            continue
        linked[a_], linked[b_] = b_, a_
        used.update((a_, b_))
    result, seen = [], set()
    for i, line in enumerate(lines):                         # strokes that were not part of any join pass through
        if i not in open_ids:
            result.append(line)

    def walk(j, entry):
        chain = []
        while j not in seen:
            seen.add(j)
            points = lines[open_ids[j]]
            chain.append(points if entry == 0 else points[::-1])
            leave = 2 * j + (1 - entry)
            if leave not in linked:
                return chain, False
            nxt = linked[leave]
            j, entry = nxt // 2, nxt % 2
        return chain, True                                    # came back to a stroke already walked: a closed loop

    for j in range(len(open_ids)):                            # chains that begin at a free end
        if j in seen:
            continue
        for entry in (0, 1):
            if 2 * j + entry not in linked:
                chain, _ = walk(j, entry)
                result.append(np.vstack(chain))
                break
    for j in range(len(open_ids)):                            # whatever is left is a ring
        if j not in seen:
            chain, _ = walk(j, 0)
            ring = np.vstack(chain)
            result.append(np.vstack([ring, ring[:1]]))
    return result


def silhouette_mask(visible):
    """The drawing's solid outline shape(s) as a boolean mask: everything that isn't paper, joined up, with the holes filled."""
    mask = cv2.morphologyEx(visible.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    count, comp, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros_like(mask)
    for c in range(1, count):
        if stats[c, cv2.CC_STAT_AREA] >= .003 * mask.size:
            keep[comp == c] = 1
    flood = keep.copy()
    h, w = keep.shape
    outside = np.zeros((h + 2, w + 2), np.uint8)
    inverse = 1 - keep
    cv2.floodFill(inverse, outside, (0, 0), 2)
    return (keep > 0) | (inverse == 1)         # holes (never reached from the corner) are part of the shape


def _order_group(strokes, width, height, outer, diagonal, low, high, start=None):
    """Order one group of (already joined) strokes: the walk round the outside, then structure part by part, then texture.
    Returns the strokes in drawing order."""
    if not len(strokes):
        return []
    ordered, drawn, pen = [], [], np.asarray(start, float) if start is not None else (np.array([float(low[0]), float(low[1])]) if outer is not None else np.array([width / 2, 0.0]))
    if outer is not None:
        shape = outer.astype(np.uint8)
        rim = shape - cv2.erode(shape, np.ones((3, 3), np.uint8))
        near = cv2.dilate(rim, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))) > 0
        height_px, width_px = near.shape

        def on_rim(points):
            xs = np.clip(points[:, 0].round().astype(int), 0, width_px - 1)
            ys = np.clip(points[:, 1].round().astype(int), 0, height_px - 1)
            return float(near[ys, xs].mean()) >= .55

        flags = [on_rim(p) for p in strokes]
        walk = [i for i, f in enumerate(flags) if f]
        while walk:                                           # one continuous walk round the outside, starting at the top left
            best = min(walk, key=lambda i: math.sqrt(pen_distance(strokes[i], pen)) + LEFT_BIAS * float(strokes[i][:, 0].min())
                       + .05 * float(strokes[i][:, 1].min()))
            walk.remove(best)
            stroke = _begin(strokes[best], pen, diagonal)
            ordered.append(stroke)
            pen = stroke[-1]
        strokes = [p for p, f in zip(strokes, flags) if not f]
    axis = float((low[0] + high[0]) / 2)
    tiers = [stroke_tier(p, diagonal) for p in strokes]
    structure = [i for i, t in enumerate(tiers) if t < 2]
    texture = [i for i, t in enumerate(tiers) if t == 2]
    parent = _parents([strokes[i] for i in structure])
    index = {k: i for k, i in enumerate(structure)}                 # position in `structure` -> stroke index
    children = {}
    for k, owner in enumerate(parent):
        children.setdefault(owner, []).append(k)


    def draw(i):
        nonlocal pen
        stroke = _begin(strokes[i], pen, diagonal)
        ordered.append(stroke)
        drawn.append(i)
        pen = stroke[-1]

    def build(group):
        pool = list(group)
        while pool:
            touching = [m for m in pool if pen_distance(strokes[index[m]], pen) <= (CONTINUE * diagonal) ** 2]
            if touching:                                            # a fragment starts where the pen is: keep tracing the contour
                k = min(touching, key=lambda m: (tiers[index[m]], pen_distance(strokes[index[m]], pen)))
                tier_now = tiers[index[k]]
            else:
                tier_now = min(tiers[index[k]] for k in pool)       # bigger shapes of this level first
                level = [k for k in pool if tiers[index[k]] == tier_now]
                k = level[_pick([strokes[index[m]] for m in level], pen, TIER_BANDS[tier_now] * height)]
            pool.remove(k)
            draw(index[k])
            twin = _twin(strokes[index[k]], [strokes[index[m]] for m in pool], axis, diagonal) if pool else None
            members = [k]
            if twin is not None:
                t = pool.pop(twin)
                draw(index[t])
                members.append(t)
            for m in members:                                       # finish this part (its inner shapes) before moving on
                build(children.get(m, []))

    build(children.get(None, []))
    # Texture: each piece goes with the part that contains it; parts are visited in the order they were drawn.
    owners = _parents([strokes[i] for i in structure] + [strokes[i] for i in texture])[len(structure):]
    by_part = {}
    for i, owner in zip(texture, owners):
        by_part.setdefault(structure[owner] if owner is not None and owner < len(structure) else None, []).append(i)
    for part in [i for i in drawn if i in by_part] + ([None] if None in by_part else []):
        for patch in _patches([strokes[i] for i in by_part[part]], diagonal):
            group = [by_part[part][k] for k in patch]
            runs = {}
            for i in group:
                points = strokes[i]
                if is_closed(points):
                    spread = np.ptp(points, axis=0)
                    angle = 0.0 if spread[0] >= spread[1] else 90.0
                else:
                    span = points[-1] - points[0]
                    angle = math.degrees(math.atan2(span[1], span[0])) % 180
                runs.setdefault(int(((angle + 11.25) % 180) // 22.5), []).append(i)
            if len(group) > 3 and max(len(v) for v in runs.values()) < .6 * len(group):
                pool = list(group)                                             # no common direction: foliage, tufts, scales...
                while pool:                                                    # the hand glides from one mark to the one beside it
                    best = min(pool, key=lambda i: pen_distance(strokes[i], pen))
                    pool.remove(best)
                    draw(best)
                continue
            for bucket in sorted(runs, key=lambda b: -len(runs[b])):       # the dominant direction first, like hatching
                theta = math.radians(bucket * 22.5)
                across = np.array([-math.sin(theta), math.cos(theta)])    # sweep across the lines of the run
                for i in sorted(runs[bucket], key=lambda i: float(strokes[i].mean(axis=0) @ across)):
                    draw(i)
    return ordered


def order_strokes_human(paths, width, height, fills=(), outer=None):
    """EXPERIMENTAL (not used by the app yet; compare it with scripts/dev/compare_order.py). Order strokes the way a person builds
    a drawing.

    0. Pieces of one outline that meet end to end are joined first (join_fragments).
    1. Structure first (major shapes and medium details), then texture last (thin lines and tiny marks).
    2. Structure is built part by part: a big shape, then the shapes inside it, each of those finished before the next
       one begins, so the head is drawn with its face before the pen moves on to the arms.
    3. A mirror twin (the other arm, leg or eye) is drawn straight after its partner.
    4. Texture is drawn patch by patch as runs of parallel lines, sweeping across the patch.
    (A fragment that starts where the pen already is carries on the contour before the pen goes anywhere else.)
    5. Every stroke starts where the pen is, in its natural direction (top first, left first, loops counter-clockwise).
    6. `fills` (groups of hatch strokes for solid black shapes) come last, after every outline, one shape at a time.
    7. With `outer` (the silhouette mask), the strokes along the outside of each shape are drawn first, as one continuous
       walk round it from the top left, before any inner feature."""
    if not len(paths):
        return []
    everything = np.vstack([np.asarray(p, float) for p in paths])
    low, high = everything.min(axis=0), everything.max(axis=0)
    diagonal = max(1.0, float(np.hypot(*(high - low))))  # the drawing, not the canvas
    strokes = join_fragments(paths, diagonal)
    # A badge or crest: a big closed ring (a frame) is drawn first, then what is inside it from the middle of the picture
    # out, and only then the fringe outside it (a wreath, a border of leaves), so the proportions are set before the decoration.
    size = high - low
    def ring(points):
        """A smooth, nearly closed loop that spans most of the picture (the gap between its ends is under a tenth of its length)."""
        if len(points) < 8 or not np.all(np.ptp(points, axis=0) >= FRAME_SHARE * size) or _smoothness(points) > FRAME_SMOOTH:
            return False
        length = float(np.sum(np.hypot(*np.diff(points, axis=0).T)))
        return float(np.hypot(*(points[0] - points[-1]))) <= .1 * length

    strokes = [np.vstack([p, p[:1]]) if (not is_closed(p) and ring(p)) else p for p in strokes]   # close a ring into one full sweep
    frames = [i for i, p in enumerate(strokes) if is_closed(p) and ring(p)]
    pieces, pen = [], None
    if frames and len(strokes) > len(frames):
        frames.sort(key=lambda i: -_area(strokes[i]))
        rings = [strokes[i] for i in frames]
        biggest = rings[0].astype(np.float32).reshape(-1, 1, 2)
        rest = [p for i, p in enumerate(strokes) if i not in frames]
        inside = [p for p in rest if cv2.pointPolygonTest(biggest, (float(p[:, 0].mean()), float(p[:, 1].mean())), False) >= 0]
        outside = [p for p in rest if not any(p is q for q in inside)]
        centre = (low + high) / 2
        pen = np.array([width / 2, 0.0])
        ordered = []
        for ring in rings:
            stroke = _begin(ring, pen, diagonal)
            ordered.append(stroke)
            pen = stroke[-1]
        inside.sort(key=lambda p: float(np.hypot(*(p.mean(axis=0) - centre))))        # nearest the middle first, then outwards
        ordered += _order_group(inside, width, height, None, diagonal, low, high, start=pen)
        if ordered:
            pen = ordered[-1][-1]
        ordered += _order_group(outside, width, height, None, diagonal, low, high, start=pen)
    else:
        ordered = _order_group(strokes, width, height, outer, diagonal, low, high)
    pen = ordered[-1][-1] if ordered else np.array([width / 2, 0.0])
    for group in fills:                                        # last of all: fill the solid black shapes in
        for stroke in group:
            ordered.append(_begin(np.asarray(stroke, float), pen, diagonal))
            pen = ordered[-1][-1]
    return ordered


