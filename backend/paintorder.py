"""EXPERIMENTAL: a colour reveal that paints region by region, the way a person colours a drawing.

The current reveal sweeps one colour at a time diagonally across the whole picture. This one paints each connected area on its
own (the shirt, then a sleeve, then the skin), finishes one before starting the next, moves to the nearest unpainted area
instead of jumping, sweeps top to bottom inside each area at a slight brush angle, and leaves the small details (eyes, stripes,
teeth) for last. Dark solid shapes (hair, boots, the mouth) are inked first, straight after the line work.

region_ranks() returns the same kind of rank map as before (0..1: when each pixel is painted), so reveal.png, paint_path and
both renderers work unchanged.
"""
import math

import cv2
import numpy as np

from .inkfill import ink_masks

BAND = .028                   # brush width as a share of the picture's longer side
BIG_AREA = .012               # share of the picture: a "big" area is painted before the small details
COLOURS = 7                   # how many colour families the non-ink picture is split into
BRUSH_ANGLE = math.radians(18)
MIN_SLICE = .004


def _chain(items, centroids, start):
    """Visit items nearest-first, beginning with the one nearest `start`."""
    order, here, left = [], np.asarray(start, float), list(items)
    while left:
        nearest = min(left, key=lambda k: float(np.hypot(*(centroids[k] - here))))
        left.remove(nearest)
        order.append(nearest)
        here = centroids[nearest]
    return order


def _colour_families(rgb, mask):
    """Group the pixels under `mask` into a few colour families (k-means in Lab). Returns an HxW label image (-1 elsewhere)."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    labels = np.full(mask.shape, -1, np.int32)
    ys, xs = np.nonzero(mask)
    if len(xs) < COLOURS * 4:
        labels[mask] = 0
        return labels
    data = lab[ys, xs]
    sample = data[np.random.default_rng(7).choice(len(data), min(len(data), 20000), replace=False)]
    cv2.setRNGSeed(7)
    _, _, centres = cv2.kmeans(sample, COLOURS, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 2, cv2.KMEANS_PP_CENTERS)
    labels[ys, xs] = np.argmin(((data[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2), axis=1)
    return labels


def region_ranks(rgb, distance, texture, texture_depth, line_width=None):
    """rgb: HxWx3 picture; distance: HxW how far each pixel is from the paper (visible change); texture: HxW streaky noise in
    -.5..+.5. Returns float32 HxW ranks in 0..1 (when each pixel is painted)."""
    height, width = distance.shape
    canvas = float(height * width)
    ranks = np.zeros((height, width), np.float32)
    visible = distance >= 14
    rgb = np.asarray(rgb, np.uint8)
    ink, thick = ink_masks(rgb, distance, line_width)
    families = _colour_families(rgb, visible & ~ink)
    big, small = [], []

    def add(mask):
        count, comp = cv2.connectedComponents(mask.astype(np.uint8), connectivity=4)
        ys_all, xs_all = np.nonzero(comp)
        labels = comp[ys_all, xs_all]
        order = np.argsort(labels, kind='stable')                 # group every component's pixels with one sort, not one scan each
        ys_all, xs_all, labels = ys_all[order], xs_all[order], labels[order]
        starts = np.searchsorted(labels, np.arange(1, count + 1))
        ends = np.searchsorted(labels, np.arange(1, count + 1), side='right')
        for c in range(count - 1):
            ys, xs = ys_all[starts[c]:ends[c]], xs_all[starts[c]:ends[c]]
            area = len(xs)
            weight = float(distance[ys, xs].sum())
            region = {'ys': ys, 'xs': xs, 'area': area, 'weight': weight, 'centroid': np.array([xs.mean(), ys.mean()])}
            (big if area >= BIG_AREA * canvas else small).append(region)

    for label in range(COLOURS):
        add(families == label)
    solid = cv2.connectedComponents(thick.astype(np.uint8), connectivity=8)
    for c in range(1, solid[0]):                           # solid black shapes (hair, boots, a sole) are painted like any colour
        mask = solid[1] == c
        if mask.sum() >= 40:
            ys, xs = np.nonzero(mask)
            big.append({'ys': ys, 'xs': xs, 'area': len(xs), 'weight': float(distance[ys, xs].sum()), 'centroid': np.array([xs.mean(), ys.mean()])})
    ranks[ink & ~thick] = 0.0                              # thin black lines are already on the page: no brush
    if not big and small:                                  # nothing large: the biggest piece leads
        small.sort(key=lambda r: -r['area'])
        big.append(small.pop(0))
    if not big:
        return ranks
    # Every small piece (an eye, a stripe, a button) is painted straight after the big area it sits in or next to.
    owner_map = np.zeros((height, width), np.int32)
    for k, r in enumerate(big):
        owner_map[r['ys'], r['xs']] = k + 1
    children = {k: [] for k in range(len(big))}
    for r in small:
        x0, x1, y0, y1 = max(0, r['xs'].min() - 4), min(width, r['xs'].max() + 5), max(0, r['ys'].min() - 4), min(height, r['ys'].max() + 5)
        window = np.zeros((y1 - y0, x1 - x0), np.uint8)
        window[r['ys'] - y0, r['xs'] - x0] = 1
        near = owner_map[y0:y1, x0:x1][cv2.dilate(window, np.ones((7, 7), np.uint8)) > 0]
        near = near[near > 0]
        if len(near):
            owner = int(np.bincount(near).argmax()) - 1
        else:
            owner = int(np.argmin([float(np.hypot(*(b['centroid'] - r['centroid']))) for b in big]))
        children[owner].append(r)
    first = max(range(len(big)), key=lambda k: big[k]['area'])      # begin with the biggest area, then the nearest next
    chain = [first] + _chain([k for k in range(len(big)) if k != first], {k: big[k]['centroid'] for k in range(len(big))}, big[first]['centroid'])
    slots = []
    for k in chain:
        slots.append(big[k])
        if children[k]:
            pieces = children[k]
            slots.append({'ys': np.concatenate([p['ys'] for p in pieces]), 'xs': np.concatenate([p['xs'] for p in pieces]),
                          'weight': sum(p['weight'] for p in pieces)})
    weights = np.array([max(r['weight'], 1e-9) for r in slots])
    weights = np.maximum(weights / weights.sum(), MIN_SLICE)
    edges = np.concatenate([[0.], np.cumsum(weights / weights.sum())])
    rng = np.random.default_rng(11)
    for slot, r in enumerate(slots):
        span = edges[slot + 1] - edges[slot]
        ranks[r['ys'], r['xs']] = edges[slot] + span * _paint_fraction(r['ys'], r['xs'], height, width, rng) * .98
    return np.clip(ranks, 0, 1).astype(np.float32)


EDGE_PX = 6               # width of the edging pass around an area, in picture pixels
EDGE_SLOWNESS = 2.5       # edging is careful work: it takes this many times longer per pixel
MIN_EDGED_AREA = 1500


def _perimeter_order(ys, xs, depth):
    """Order the pixels of an area's rim by their place along its outline, starting from the top left and going clockwise."""
    y0, x0 = ys.min() - 2, xs.min() - 2
    mask = np.zeros((ys.max() - y0 + 3, xs.max() - x0 + 3), np.uint8)
    mask[ys - y0, xs - x0] = 1
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return np.arange(len(ys))
    contour = max(contours, key=len).reshape(-1, 2).astype(np.float32)
    start = int(np.argmin(contour[:, 1] + .5 * contour[:, 0]))
    contour = np.roll(contour, -start, axis=0)
    points = np.stack([xs - x0, ys - y0], axis=1).astype(np.float32)
    nearest = np.empty(len(points), np.int32)
    for i in range(0, len(points), 1500):
        chunk = points[i:i + 1500]
        nearest[i:i + 1500] = np.argmin(((chunk[:, None, :] - contour[None, :, :]) ** 2).sum(axis=2), axis=1)
    return np.argsort(nearest, kind='stable')


def _paint_fraction(ys, xs, height, width, rng):
    """When, from 0 to 1 over the time spent on this area, each of its pixels is painted: the rim first, as a careful pass round
    the edge, then the inside in strokes along the area's long direction, every stroke left to right, from the top down."""
    count = len(ys)
    fraction = np.zeros(count, np.float32)
    interior = np.ones(count, bool)
    edge_weight = 0.0
    if count >= MIN_EDGED_AREA:
        y0, x0 = ys.min() - 2, xs.min() - 2
        mask = np.zeros((ys.max() - y0 + 3, xs.max() - x0 + 3), np.uint8)
        mask[ys - y0, xs - x0] = 1
        inner = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * EDGE_PX + 1, 2 * EDGE_PX + 1)))
        rim = inner[ys - y0, xs - x0] == 0
        if rim.sum() > 20 and (~rim).sum() > 0:
            interior = ~rim
            edge_weight = EDGE_SLOWNESS * float(rim.sum())
    total = edge_weight + float(interior.sum())
    cursor = 0.0
    if edge_weight:
        order = _perimeter_order(ys[~interior], xs[~interior], EDGE_PX)
        rank = np.empty(len(order), np.float32)
        rank[order] = np.arange(len(order)) / len(order)
        fraction[~interior] = rank * (edge_weight / total)
        cursor = edge_weight / total
    iy, ix = ys[interior].astype(np.float32), xs[interior].astype(np.float32)
    centred = np.stack([ix - ix.mean(), iy - iy.mean()], axis=1)
    if len(centred) > 2:
        eigenvalues, vectors = np.linalg.eigh(np.cov(centred.T))
        major = vectors[:, 1]
    else:
        major = np.array([1.0, 0.0])
    if abs(major[0]) < .2:                                   # a tall area: strokes run downwards
        major = major if major[1] > 0 else -major
    else:                                                    # otherwise strokes run left to right
        major = major if major[0] > 0 else -major
    minor = np.array([-major[1], major[0]])
    if minor[1] < 0 or (abs(minor[1]) < .2 and minor[0] < 0):
        minor = -minor
    across = centred @ minor
    along = centred @ major
    across -= across.min()
    widths = BAND * max(height, width) * (.75 + .5 * rng.random(int(across.max() / (BAND * max(height, width) * .75)) + 3))
    bounds = np.cumsum(widths)
    band = np.searchsorted(bounds, across)
    local = np.zeros(len(band), np.float32)
    offset = 0
    for b in np.unique(band):
        members = np.nonzero(band == b)[0]
        order = np.argsort(along[members], kind='stable')      # always left to right, so the hand stays over unpainted paper
        local[members[order]] = offset + np.arange(len(members))
        offset += len(members)
    fraction[interior] = cursor + local / max(1.0, float(offset)) * (1 - cursor)
    return fraction
