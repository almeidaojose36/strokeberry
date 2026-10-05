"""Find the artwork's real black outlines and turn each one into a single centre-line stroke.

The older method traced the edge of every colour region, which draws each line twice (both sides of it) and also draws
boundaries the artist never inked. Here only genuinely dark, thin marks become strokes; big dark areas (a pupil, a black
sole) are left for the colour phase to paint. Returns None when the picture has no usable outlines (a photo, pastel art),
so the caller can fall back to edge tracing."""
import math

import cv2
import numpy as np

MAX_STROKES = 800  # a very textured picture keeps its longest lines
MIN_COVERAGE = .4  # share of strong colour boundaries that must lie beside a drawn outline
NEIGHBOURS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


def ink_mask(rgb, gray):
    """Pen-black pixels: dark and not strongly coloured, so deep red or teal fills are not mistaken for outlines."""
    spread = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2)
    return (gray < 125) & (spread < 80)


def ink_mask_no_green(rgb, gray):
    """Like ink_mask but without dark GREEN pixels. A dark green fill (the leaves of a wreath, a roof) is not a pen line, and thinning
    it breaks it into dashes; used only as a second try when the normal rule finds no usable outlines."""
    r, g, b = (rgb[..., k].astype(np.int16) for k in range(3))
    return ink_mask(rgb, gray) & ~((g > r + 10) & (g > b + 6))


def thin(binary):
    """Zhang-Suen thinning: reduce every stroke to a one-pixel-wide centre line."""
    image = (binary > 0).astype(np.uint8)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            p = np.pad(image, 1)
            p1, p2, p3, p4, p5, p6, p7, p8, p9 = (p[1:-1, 1:-1], p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:],
                                                 p[2:, 1:-1], p[2:, :-2], p[1:-1, :-2], p[:-2, :-2])
            around = [p2, p3, p4, p5, p6, p7, p8, p9]
            count = sum(a.astype(np.int16) for a in around)
            turns = sum(((around[k] == 0) & (around[(k + 1) % 8] == 1)).astype(np.int16) for k in range(8))
            if step == 0:
                gate = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                gate = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            remove = (p1 == 1) & (count >= 2) & (count <= 6) & (turns == 1) & gate
            if remove.any():
                image[remove] = 0
                changed = True
    return image


def prune_redundant(skeleton):
    """Delete pixels that add nothing to connectivity (the inner corner of a staircase), so a diagonal line is a clean
    chain of two-neighbour pixels instead of a string of false junctions. Endpoints are never touched."""
    image = np.pad(skeleton.astype(np.uint8), 1)
    ring = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    changed = True
    while changed:
        changed = False
        for y, x in zip(*np.nonzero(image)):
            around = [(dy, dx) for dy, dx in ring if image[y + dy, x + dx]]
            if len(around) < 2:
                continue
            # are all the neighbours still linked to one another if this pixel goes?
            groups = []
            for cell in around:
                touching = [g for g in groups if any(max(abs(cell[0] - o[0]), abs(cell[1] - o[1])) == 1 for o in g)]
                merged = [cell] + [o for g in touching for o in g]
                groups = [g for g in groups if g not in touching] + [merged]
            if len(groups) == 1:
                image[y, x] = 0
                changed = True
    return image[1:-1, 1:-1]


def trace(skeleton, min_length=8):
    """Walk a one-pixel skeleton into polylines (chains between endpoints/junctions, plus closed loops)."""
    height, width = skeleton.shape
    pixels = set(zip(*np.nonzero(skeleton)))  # (y, x)

    def around(pixel):
        y, x = pixel
        return [(y + dy, x + dx) for dy, dx in NEIGHBOURS if (y + dy, x + dx) in pixels]

    degree = {pixel: len(around(pixel)) for pixel in pixels}
    nodes = {pixel for pixel, d in degree.items() if d != 2}
    used_edges, visited, chains = set(), set(), []
    for node in sorted(nodes):
        for first in around(node):
            if frozenset((node, first)) in used_edges:
                continue
            chain, previous, current = [node, first], node, first
            used_edges.add(frozenset((node, first)))
            while current not in nodes:
                options = [q for q in around(current) if q != previous and frozenset((current, q)) not in used_edges]
                if not options:
                    break
                following = min(options, key=lambda q: (abs(q[0] - current[0]) + abs(q[1] - current[1]), q))
                used_edges.add(frozenset((current, following)))
                previous, current = current, following
                chain.append(current)
            visited.update(chain)
            chains.append((chain, degree[node], degree[chain[-1]]))
    # closed loops have no endpoint or junction to start from
    for start in sorted(pixels - visited):
        if start in visited:
            continue
        chain, previous, current = [start], None, start
        while True:
            options = [q for q in around(current) if q != previous and q not in visited]
            if not options:
                break
            previous, current = current, options[0]
            visited.add(current)
            chain.append(current)
        if len(chain) > 4 and math.dist(chain[0], chain[-1]) < 3:
            chain.append(chain[0])
        chains.append((chain, 2, 2))
    result = []
    for chain, start_degree, end_degree in chains:
        # a short spur that ends freely at a junction is skeleton noise, not a drawn line
        spur = len(chain) < 10 and (start_degree == 1) != (end_degree == 1)
        if len(chain) >= min_length and not spur:
            result.append(np.array([(x, y) for y, x in chain], float))
    return result


def extract_strokes(rgb, mask=None):
    """Centre-line strokes for the artwork's dark outlines, or None if it has none worth drawing. `mask` picks which pixels
    count as pen ink (default: ink_mask)."""
    from .artistry import smooth_path

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    dark = np.uint8((mask or ink_mask)(rgb, gray)) * 255
    if not 0.004 <= dark.mean() / 255 <= 0.30:
        return None
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    # How wide are the outlines? Big blobs (pupils, soles) are fills to paint later, not lines to draw.
    distance = cv2.distanceTransform(dark, cv2.DIST_L2, 3)
    peaks = distance[(cv2.dilate(distance, np.ones((5, 5), np.uint8)) == distance) & (distance > 0)]
    if not len(peaks):
        return None
    line_half_width = float(np.median(peaks))
    radius = max(2, int(round(line_half_width * 1.9)))
    thick = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1)))
    fills = thick
    lines = cv2.bitwise_and(dark, cv2.bitwise_not(cv2.dilate(fills, np.ones((3, 3), np.uint8))))
    lines = cv2.morphologyEx(lines, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))  # drop crumbs left beside fills
    count, labels, stats, _ = cv2.connectedComponentsWithStats(lines, 8)
    keep = np.zeros(count, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= max(20, 4 * line_half_width)
    lines = np.uint8(keep[labels]) * 255
    if lines.mean() / 255 < .0015:
        return None
    paths = []
    for stroke in trace(prune_redundant(thin(lines))):
        approx = cv2.approxPolyDP(stroke.astype(np.float32).reshape(-1, 1, 2), 0.9, False).reshape(-1, 2)
        if len(approx) >= 2:
            paths.append(smooth_path(approx))
    if len(paths) < 4:
        return None
    paths += outline_fills(dark, paths, line_half_width)
    # Only trust the outlines if they account for most of the picture's strong colour boundaries; otherwise (a black
    # body merging into its outline, a picture with soft edges) the drawing would look half empty, so use edge tracing.
    drawn = np.zeros(gray.shape, np.uint8)
    for stroke in paths:
        cv2.polylines(drawn, [np.round(stroke).astype(np.int32)], False, 255, 1)
    reach = 2 * int(np.ceil(line_half_width)) + 5  # bold outlines have their edges further from the centre line
    near = cv2.dilate(drawn, np.ones((reach, reach), np.uint8)) > 0
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 45, 125) > 0
    smooth = cv2.GaussianBlur(rgb, (0, 0), 1.2).astype(np.float32)
    strength = np.hypot(np.abs(np.diff(smooth, axis=1, prepend=smooth[:, :1])).sum(axis=2),
                        np.abs(np.diff(smooth, axis=0, prepend=smooth[:1])).sum(axis=2))
    strong = (strength > 60) & edges
    if strong.any() and float(near[strong].mean()) < MIN_COVERAGE:
        return None
    return sorted(paths, key=len, reverse=True)[:MAX_STROKES], 2 * line_half_width


def outline_fills(dark, paths, line_half_width):
    """Closed outlines around dark shapes the centre lines don't cover (nose, mouth, pupils, collar, dark patches), so
    every hard edge is inked in the line phase and only the flat colour is left for painting."""
    from .artistry import smooth_path

    drawn = np.zeros(dark.shape, np.uint8)
    for stroke in paths:
        cv2.polylines(drawn, [np.round(stroke).astype(np.int32)], False, 255, 1)
    reach = int(round(2 * line_half_width)) + 2
    covered = cv2.dilate(drawn, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * reach + 1, 2 * reach + 1)))
    left = cv2.bitwise_and(dark, cv2.bitwise_not(covered))
    left = cv2.morphologyEx(left, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(left, 8)
    extra, streaks = [], np.zeros_like(left)
    for label in range(1, count):
        area = stats[label, cv2.CC_STAT_AREA]
        if area < max(16, 3 * line_half_width ** 2):
            continue
        piece = np.uint8(labels == label) * 255
        thickness = float(cv2.distanceTransform(piece, cv2.DIST_L2, 3).max())
        reach_of = float(np.hypot(stats[label, cv2.CC_STAT_WIDTH], stats[label, cv2.CC_STAT_HEIGHT]))
        if reach_of > 5 * thickness:
            streaks |= piece  # a stretch of outline that came out too thick to trace: draw its centre line
            continue
        contours, _ = cv2.findContours(piece, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for contour in contours:
            approx = cv2.approxPolyDP(contour, 1.2, True).reshape(-1, 2)
            if len(approx) >= 3:
                extra.append(smooth_path(np.vstack([approx, approx[:1]])))
    for stroke in trace(prune_redundant(thin(streaks))):
        approx = cv2.approxPolyDP(stroke.astype(np.float32).reshape(-1, 1, 2), 0.9, False).reshape(-1, 2)
        if len(approx) >= 2:
            extra.append(smooth_path(approx))
    return extra


def edge_strokes(rgb):
    """Fallback for pictures with no usable black outlines (photos, pastel or shaded art): trace the colour edges, but as
    single centre lines. The older contour tracing walked both sides of every edge, which doubled each line."""
    from .artistry import smooth_path

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 45, 125)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8))  # close hairline gaps so one edge stays one stroke
    paths = []
    for stroke in trace(prune_redundant(thin(edges)), min_length=10):
        approx = cv2.approxPolyDP(stroke.astype(np.float32).reshape(-1, 1, 2), 1.0, False).reshape(-1, 2)
        if len(approx) >= 2:
            paths.append(smooth_path(approx))
    return sorted(paths, key=len, reverse=True)[:MAX_STROKES]


def missing_lines(rgb, paths, line_width):
    """Suggested extra lines: strong colour boundaries (fur tufts, tail tips, inner ears, folds) that the artwork left
    without a dark line. Returns single centre-line strokes, or [] when the outlines already cover the picture."""
    from .artistry import smooth_path

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    lab = cv2.cvtColor(cv2.GaussianBlur(rgb, (0, 0), 1.0), cv2.COLOR_RGB2LAB).astype(np.float32)
    strength = np.sqrt((cv2.Sobel(lab, cv2.CV_32F, 1, 0) ** 2 + cv2.Sobel(lab, cv2.CV_32F, 0, 1) ** 2).sum(axis=2))
    edge = (strength > max(60, float(np.percentile(strength, 90)))) & (gray < 250)
    drawn = np.zeros(gray.shape, np.uint8)
    for stroke in paths:
        cv2.polylines(drawn, [np.round(stroke).astype(np.int32)], False, 255, 1)
    reach = int(round(line_width)) * 2 + 5
    covered = cv2.dilate(np.uint8(ink_mask(rgb, gray)) | (drawn > 0), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (reach, reach))) > 0
    gaps = cv2.dilate(np.uint8(edge & ~covered) * 255, np.ones((3, 3), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(gaps, 8)
    keep = np.zeros(count, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 60
    gaps = np.uint8(keep[labels]) * 255
    suggested = []
    for stroke in trace(prune_redundant(thin(gaps)), min_length=14):
        approx = cv2.approxPolyDP(stroke.astype(np.float32).reshape(-1, 1, 2), 1.2, False).reshape(-1, 2)
        if len(approx) >= 2:
            suggested.append(smooth_path(approx))
    suggested = sorted(suggested, key=len, reverse=True)[:60]
    length = lambda s: float(np.linalg.norm(np.diff(s, axis=0), axis=1).sum())
    existing = sum(length(s) for s in paths) or 1.
    added = sum(length(s) for s in suggested)
    return suggested if suggested and added >= .04 * existing else []
