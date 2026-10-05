"""EXPERIMENTAL: let the pen fill solid black shapes (hair, boots, a mouth) with a back-and-forth hatch, as a person would.

The tracer only draws outlines and centre lines, so a solid dark area was drawn as its outline and filled in later during
the colour phase. fill_strokes() returns the pen strokes that fill each such area: parallel lines at 45 degrees, spaced just
under the pen's width, joined into one zig-zag per area so the pen doesn't lift between lines.
"""
import math

import cv2
import numpy as np

INK_LUMINANCE = 70
INK_SPREAD = 45
MIN_AREA = 60          # smaller dark specks are not filled
MARKER = 2.6           # the fill is done with a marker this many times wider than the outline pen


def ink_masks(rgb, distance, line_width=None):
    """(ink, thick): near-black neutral pixels, and the part of them that is a solid shape rather than a line. A shape is solid
    when it is clearly thicker than the picture's own outlines (`line_width`, as measured by the tracer), so a picture drawn with
    heavy black outlines doesn't have its outlines mistaken for fills."""
    rgb = np.asarray(rgb, np.uint8)
    luminance = rgb @ np.array([.299, .587, .114], np.float32)
    spread = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2).astype(np.int16)
    ink = (distance >= 14) & (luminance < INK_LUMINANCE) & (spread < INK_SPREAD)
    size = max(7, int(round(2.6 * float(line_width or 0))) | 1)
    thick = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)))
    thick = cv2.dilate(thick, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))).astype(bool) & ink
    return ink, thick


def _runs(row):
    padded = np.concatenate([[0], row.astype(np.int8), [0]])
    change = np.diff(padded)
    return list(zip(np.nonzero(change == 1)[0], np.nonzero(change == -1)[0] - 1))


def fill_strokes(thick, line_width, angle_degrees=45):
    """For every solid dark area in the boolean mask `thick`, the zig-zag hatch strokes (lists of [x, y]) that fill it: a list of
    strokes per area, areas ordered from the top-left."""
    spacing = max(2.0, .8 * MARKER * float(line_width))
    inset = max(1, round(.45 * MARKER * float(line_width)))   # keep the wide marker inside the shape, so its edge stays crisp
    thick = cv2.erode(thick.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * inset + 1, 2 * inset + 1))).astype(bool)
    count, comp = cv2.connectedComponents(thick.astype(np.uint8), connectivity=8)
    height, width = thick.shape
    centre = (width / 2, height / 2)
    side = int(math.hypot(width, height)) + 4
    forward = cv2.getRotationMatrix2D(centre, angle_degrees, 1.0)
    forward[:, 2] += [(side - width) / 2, (side - height) / 2]
    inverse = cv2.invertAffineTransform(forward)
    groups = []
    for c in range(1, count):
        mask = comp == c
        if mask.sum() < MIN_AREA:
            continue
        rotated = cv2.warpAffine(mask.astype(np.uint8), forward, (side, side), flags=cv2.INTER_NEAREST) > 0
        rows = np.nonzero(rotated.any(axis=1))[0]
        chain, last = [], None
        done = []
        for y in np.arange(rows.min(), rows.max() + 1, spacing):
            runs = [r for r in _runs(rotated[int(round(y))]) if r[1] - r[0] >= 2]
            for x0, x1 in runs:
                if chain and last is not None and x0 - spacing * 2 <= last <= x1 + spacing * 2:
                    chain.append((last, y))                        # step down to the next line without lifting the pen
                    ends = (x1, x0) if abs(last - x0) > abs(last - x1) else (x0, x1)
                    chain.extend([(ends[0], y), (ends[1], y)])
                    last = ends[1]
                    continue
                if chain:
                    done.append(chain)
                chain = [(x0, y), (x1, y)]
                last = x1
        if chain:
            done.append(chain)
        group = [cv2.transform(np.array([chain], np.float32), inverse)[0] for chain in done]
        if group:
            groups.append(group)
    return sorted(groups, key=lambda g: (round(min(float(p[:, 1].min()) for p in g) / 40), min(float(p[:, 0].min()) for p in g)))


def outline_strokes(thick, epsilon=1.0):
    """The outline of every solid dark shape (hair, boots, a black sole) as a closed pen stroke, so the line phase shows the full
    silhouette of these shapes. Returns (strokes, mask): the closed outlines, and a boolean mask of the shapes they enclose."""
    contours, _ = cv2.findContours(thick.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    strokes = []
    for contour in contours:
        if cv2.contourArea(contour) < MIN_AREA:
            continue
        points = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2).astype(float)
        if len(points) >= 3:
            strokes.append(np.vstack([points, points[:1]]))
    return strokes


def inside_share(points, mask):
    """Share of a stroke's points that lie on the boolean mask."""
    xs = np.clip(np.asarray(points)[:, 0].round().astype(int), 0, mask.shape[1] - 1)
    ys = np.clip(np.asarray(points)[:, 1].round().astype(int), 0, mask.shape[0] - 1)
    return float(mask[ys, xs].mean())
