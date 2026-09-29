"""Panel crops, conservative registration, and progressive stage differences."""
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .artistry import clean_paths, make_timeline, event_position, SCENE_VERSION

PAPER = np.array([250, 249, 246], dtype=np.uint8)
REVEAL_VERSION = 5
COLOR_NAMES = ['Paper & dark fill', 'Blue', 'Yellow', 'Green', 'Red', 'Orange', 'Pink', 'Purple', 'Gray shading', 'Labels & guides', 'Main subject', 'Environment']
PASS_ORDER = [9, 10, 11, 0, 1, 2, 3, 4, 5, 6, 7, 8]


def color_layers(target, regions=None):
    """Stable pigment families: keep textured shades of one hue together."""
    hsv = cv2.cvtColor(target, cv2.COLOR_RGB2HSV)
    hue, saturation, value = cv2.split(hsv)
    labels = np.zeros(hue.shape, np.uint8)
    colored = (saturation >= 30) & (value >= 55)
    labels[colored & ((hue < 10) | (hue >= 175))] = 4
    labels[colored & (hue >= 10) & (hue < 22)] = 5
    labels[colored & (hue >= 22) & (hue < 38)] = 2
    labels[colored & (hue >= 38) & (hue < 85)] = 3
    labels[colored & (hue >= 85) & (hue < 135)] = 1
    labels[colored & (hue >= 135) & (hue < 155)] = 7
    labels[colored & (hue >= 155) & (hue < 175)] = 6
    labels[(saturation < 30) & (value >= 65) & (value < 220)] = 8
    # Treat dark strokes and their antialiased gray edges as one structural pass.
    # Otherwise gray edges wait until shading, leaving broken-looking outlines.
    gray = cv2.cvtColor(target, cv2.COLOR_RGB2GRAY)
    dark = np.uint8((gray < 100) & (saturation < 80))
    distance = cv2.distanceTransform(dark, cv2.DIST_L2, 5)
    narrow = np.uint8((dark > 0) & (distance <= 4))
    nearby = cv2.dilate(narrow, np.ones((5,5),np.uint8)) > 0
    structure = nearby & (gray < 225) & (saturation < 80)
    # Thin colored connected marks (e.g. lettering) also precede broad fills.
    for color in range(1,8):
        pigment = np.uint8(labels == color)
        count, components, stats, _ = cv2.connectedComponentsWithStats(pigment, 8)
        thickness = cv2.distanceTransform(pigment, cv2.DIST_L2, 5)
        maxima = np.zeros(count)
        np.maximum.at(maxima, components.ravel(), thickness.ravel())
        keep = (stats[:,cv2.CC_STAT_AREA] >= 12) & (maxima <= 2.5)
        keep[0] = False
        structure |= keep[components]
    labels[structure] = 9
    if regions is not None:
        prioritize_subject(labels, target, regions)
    return labels


def prioritize_subject(labels, target, regions):
    """Estimate a subject silhouette per panel; separate it from outside scenery.

    This is geometric grouping, not OCR or semantic object recognition. Opening
    the filled silhouette removes thin ground lines attached to the character.
    """
    for x0,y0,x1,y1 in regions:
        local = labels[y0:y1,x0:x1]
        gray = cv2.cvtColor(target[y0:y1,x0:x1], cv2.COLOR_RGB2GRAY)
        h,w = gray.shape
        ink = np.uint8(gray < 130)*255
        # Ignore panel dividers when estimating the character silhouette.
        margin = max(2, round(min(h,w)*.012))
        ink[:margin]=0;ink[-margin:]=0;ink[:,:margin]=0;ink[:,-margin:]=0
        contours,_ = cv2.findContours(ink,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        candidates=[]
        for c in contours:
            area=cv2.contourArea(c)
            x,y,cw,ch=cv2.boundingRect(c)
            if area < h*w*.025 or cw > w*.96 or ch > h*.96: continue
            cx,cy=x+cw/2,y+ch/2
            centrality=1+abs(cx/w-.5)+abs(cy/h-.58)
            candidates.append((area/centrality,c))
        subject=np.zeros((h,w),np.uint8)
        if candidates:
            contour=max(candidates,key=lambda item:item[0])[1]
            cv2.drawContours(subject,[contour],-1,255,cv2.FILLED)
            size=max(3,round(min(h,w)*.03)|1)
            subject=cv2.morphologyEx(subject,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(size,size)))
            subject=cv2.dilate(subject,np.ones((5,5),np.uint8))
        structure=local==9
        local[structure]=11
        local[structure & (subject>0)]=10
        # Compact annotations in the top-left corner, plus long panel rules.
        count, components, stats, _=cv2.connectedComponentsWithStats(np.uint8(structure),8)
        for i in range(1,count):
            x,y,cw,ch,area=stats[i]
            annotation=(x+cw < w*.25 and y+ch < h*.24 and ch < h*.18 and area>=3)
            rule=(cw>w*.85 and ch<h*.025) or (ch>h*.85 and cw<w*.025)
            if annotation or rule:
                local[components==i]=9
        horizontal=cv2.morphologyEx(np.uint8(structure),cv2.MORPH_OPEN,np.ones((1,max(3,round(w*.85))),np.uint8))
        vertical=cv2.morphologyEx(np.uint8(structure),cv2.MORPH_OPEN,np.ones((max(3,round(h*.85)),1),np.uint8))
        local[(horizontal>0)|(vertical>0)]=9


def reading_regions(image):
    """Split full-sheet drawing paths at long rules or whitespace gutters."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    ink = gray < 150
    def cuts(values, length):
        indices = np.flatnonzero(values > .75)
        groups = np.split(indices, np.where(np.diff(indices) > 1)[0]+1)
        return [round(float(g.mean())) for g in groups if len(g) and .08*length < g.mean() < .92*length]
    xs, ys = cuts(ink.mean(axis=0), w), cuts(ink.mean(axis=1), h)
    if not xs and not ys:
        xb, yb = occupied_bands(ink.sum(axis=0)), occupied_bands(ink.sum(axis=1))
        if 2 <= len(xb)*len(yb) <= 8:
            xs = [round((a[1]+b[0])/2) for a,b in zip(xb,xb[1:])]
            ys = [round((a[1]+b[0])/2) for a,b in zip(yb,yb[1:])]
    if (len(xs)+1)*(len(ys)+1) > 8:
        xs, ys = [], []
    xs, ys = [0]+xs+[w], [0]+ys+[h]
    return [(x0,y0,x1,y1) for y0,y1 in zip(ys,ys[1:]) for x0,x1 in zip(xs,xs[1:])]


def swept_scene(previous, target, regions, labels=None):
    """Trace detail, then hatch uncovered pixels. No nearest-path reveal."""
    paths, clips, colors = [], [], []
    if labels is None: labels = color_layers(target, regions)
    for (x0,y0,x1,y1), color in [(region,color) for region in regions for color in PASS_ORDER]:
        changed = np.uint8(np.any(previous[y0:y1,x0:x1] != target[y0:y1,x0:x1], axis=2) & (labels[y0:y1,x0:x1] == color))*255
        if not np.any(changed): continue
        edges = cv2.Canny(cv2.cvtColor(target[y0:y1,x0:x1], cv2.COLOR_RGB2GRAY), 60, 140)
        edges[changed == 0] = 0
        contours,_ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        detail = clean_paths(contours, changed.shape)
        detail.sort(key=lambda p: (float(p[:,1].min()), float(p[:,0].min())))
        covered = np.zeros_like(changed)
        local_paths = list(detail)
        for path in detail:
            cv2.polylines(covered,[np.rint(path).astype(np.int32)],False,255,6)
        # Each run is swept by the same six-pixel brush used by both renderers.
        for y in range(changed.shape[0]):
            remaining = (changed[y] > 0) & (covered[y] == 0)
            indices = np.flatnonzero(remaining)
            for group in np.split(indices, np.where(np.diff(indices)>1)[0]+1):
                if not len(group): continue
                a, b = int(group[0]), int(group[-1])
                path = np.array([[a,y],[max(a+.01,b),y]],float)
                local_paths.append(path)
                cv2.line(covered,(a,y),(b,y),255,6)
        for path in local_paths:
            paths.append((path+[x0,y0]).tolist())
            clips.append([x0,y0,x1,y1])
            colors.append(color)
    timeline = make_timeline(paths)
    path_index = 0
    for event in timeline:
        if event['kind'] == 'lift': path_index += 1
        event['clip'] = clips[path_index]
        event['color'] = colors[path_index]
    return timeline, len(paths)


def original_path(folder):
    original = folder / 'original.png'
    return original if original.exists() else folder / 'source.png'


def occupied_bands(values):
    """Join small gaps within drawings, retaining wide whitespace gutters."""
    active = np.uint8(values > max(2, values.max() * .006))
    length = len(active)
    active = cv2.morphologyEx(active.reshape(1, -1), cv2.MORPH_CLOSE,
                             np.ones((1, max(3, round(length * .035))), np.uint8)).ravel()
    edges = np.diff(np.concatenate([[0], active, [0]]))
    return [(int(a), int(b)) for a, b in zip(np.where(edges == 1)[0], np.where(edges == -1)[0])
            if b-a > length * .06]


def four_step_reading_order(stages):
    """Return four tutorial panels in natural reading order.

    Horizontal strips read left-to-right, vertical strips read top-to-bottom,
    and the usual 2×2 sheet reads top-left, top-right, bottom-left,
    bottom-right. Stage metadata stays attached to its crop.
    """
    if len(stages) != 4:
        return list(stages)
    def center(stage):
        crop = stage['crop'] if isinstance(stage, dict) else stage
        return crop['x'] + crop['width'] / 2, crop['y'] + crop['height'] / 2
    points = [center(stage) for stage in stages]
    x_span = max(x for x, _ in points) - min(x for x, _ in points)
    y_span = max(y for _, y in points) - min(y for _, y in points)
    if y_span < max(.04, x_span * .2):
        return sorted(stages, key=lambda stage: center(stage)[0])
    if x_span < max(.04, y_span * .2):
        return sorted(stages, key=lambda stage: center(stage)[1])
    by_row = sorted(stages, key=lambda stage: center(stage)[1])
    return sorted(by_row[:2], key=lambda stage: center(stage)[0]) + \
           sorted(by_row[2:], key=lambda stage: center(stage)[0])


def detect_panels(folder):
    image = np.array(Image.open(original_path(folder)).convert('RGB'))
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    mask = np.uint8(gray > 95) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    height, width = gray.shape
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w * h > width * height * .035 and w > width * .12 and h > height * .1:
            boxes.append((x, y, w, h))
    # Bordered tutorial panels on a dark background.
    if 2 <= len(boxes) <= 8:
        boxes = four_step_reading_order([
            {'crop': {'x': x/width, 'y': y/height, 'width': w/width, 'height': h/height},
             'box': (x, y, w, h)} for x, y, w, h in boxes
        ]) if len(boxes) == 4 else sorted(boxes, key=lambda b: (b[1], b[0]))
        if boxes and isinstance(boxes[0], dict):
            boxes = [item['box'] for item in boxes]
        row_starts = []
        for _, y, _, h in boxes:
            if not row_starts or abs(y-row_starts[-1]) > h*.2:
                row_starts.append(y)
        rows = len(row_starts)
        return {'detected': True, 'method': 'borders', 'rows': rows, 'columns': len(boxes)//rows,
                'width': width, 'height': height,
                'crops': [{'x': (x+3)/width, 'y': (y+3)/height,
                           'width': (w-6)/width, 'height': (h-6)/height} for x,y,w,h in boxes]}
    # Borderless tutorials: look for gutters between groups of ink, not paper.
    ink = np.uint8(gray < 200)
    xs, ys = occupied_bands(ink.sum(axis=0)), occupied_bands(ink.sum(axis=1))
    count = len(xs) * len(ys)
    if 2 <= count <= 8 and len(xs) <= 4 and len(ys) <= 4:
        xcuts = [0] + [(left[1]+right[0])/2 for left,right in zip(xs,xs[1:])] + [width]
        ycuts = [0] + [(top[1]+bottom[0])/2 for top,bottom in zip(ys,ys[1:])] + [height]
        crops = [{'x': xcuts[x]/width, 'y': ycuts[y]/height,
                  'width': (xcuts[x+1]-xcuts[x])/width, 'height': (ycuts[y+1]-ycuts[y])/height}
                 for y in range(len(ys)) for x in range(len(xs))]
        # Do not confidently split a single drawing with blank corners into a grid.
        if all(np.count_nonzero(ink[round(c['y']*height):round((c['y']+c['height'])*height),
                                    round(c['x']*width):round((c['x']+c['width'])*width)]) > width*height*.0003 for c in crops):
            return {'detected': True, 'method': 'whitespace', 'rows': len(ys), 'columns': len(xs),
                    'width': width, 'height': height, 'crops': crops}
    return fallback_layout(width, height)


def fallback_layout(width, height, columns=1, rows=1):
    """No panels found: keep the whole image as one step (or use a known grid, e.g. a gallery tutorial sheet)."""
    return {'detected': False, 'method': 'fallback', 'rows': rows, 'columns': columns,
            'width': width, 'height': height,
            'crops': [{'x': x/columns, 'y': y/rows, 'width': 1/columns, 'height': 1/rows}
                      for y in range(rows) for x in range(columns)]}


def normalize_paper(rgb):
    rgb = cv2.medianBlur(rgb, 3)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    background = cv2.GaussianBlur(cv2.dilate(gray, np.ones((35, 35), np.uint8)), (0, 0), 12)
    normalized = np.clip(rgb.astype(float) * PAPER / np.maximum(background[..., None], 110), 0, 255)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    foreground = np.uint8((gray.astype(float) <= background.astype(float) - 35) | (hsv[:, :, 1] >= 45))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(foreground, 8)
    keep = np.zeros(count, dtype=bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 10
    normalized[~keep[labels]] = PAPER
    return normalized.astype(np.uint8)


def line_mask(image):
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return np.uint8(gray < 125) * 255


def alignment(image, reference):
    """Fit translation and uniform scale by one-way chamfer distance.

    Earlier steps contain less detail, so we only score their marks against the
    final stage, not missing future marks against the earlier drawing.
    """
    height, width = image.shape[:2]
    points = np.column_stack(np.where(line_mask(image) > 0))[:, ::-1].astype(float)
    if len(points) < 12 or np.count_nonzero(line_mask(reference)) < 12:
        return 0., 0., 1., 0.
    points = points[::max(1, len(points) // 1600)]
    distances = cv2.distanceTransform(255 - line_mask(reference), cv2.DIST_L2, 3)
    center = np.array([width / 2, height / 2])
    def score(dx, dy, scale):
        moved = (points - center) * scale + center + [dx, dy]
        x, y = np.rint(moved).astype(int).T
        inside = (x >= 0) & (x < width) & (y >= 0) & (y < height)
        residual = np.full(len(points), 18.)
        residual[inside] = distances[y[inside], x[inside]]
        return float(np.minimum(residual, 18).mean()) + .008 * (abs(dx) + abs(dy)) + abs(1-scale) * 3
    best = (score(0, 0, 1), 0., 0., 1.)
    for scale in [.9, .95, 1., 1.05, 1.1]:
        for dy in range(-60, 61, 12):
            for dx in range(-48, 49, 12):
                candidate = (score(dx, dy, scale), float(dx), float(dy), scale)
                if candidate[0] < best[0]:
                    best = candidate
    _, bx, by, bs = best
    for scale in sorted(set([1.] + [round(float(s), 3) for s in np.arange(max(.88, bs-.05), min(1.12, bs+.05)+.001, .01)])):
        for dy in range(round(by)-8, round(by)+9, 4):
            for dx in range(round(bx)-8, round(bx)+9, 4):
                candidate = (score(dx, dy, scale), float(dx), float(dy), scale)
                if candidate[0] < best[0]:
                    best = candidate
    error, dx, dy, scale = best
    confidence = max(0., min(1., 1 - error / 12))
    return dx, dy, scale, round(confidence, 2)


def difference_scene(previous, target):
    delta = np.max(np.abs(target.astype(float) - previous.astype(float)), axis=2)
    changed = np.uint8(delta > 18) * 255
    target = np.where(changed[..., None] > 0, target, previous).astype(np.uint8)
    contours, _ = cv2.findContours(changed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=lambda c: cv2.arcLength(c, True), reverse=True)
    paths = clean_paths(contours, changed.shape)
    ordered, current = [], np.array([0, 0])
    while paths:
        distances = [float(np.linalg.norm(p[0] - current)) for p in paths]
        p = paths.pop(int(np.argmin(distances)))
        ordered.append(p.tolist())
        current = p[-1]
    timeline = make_timeline(ordered)
    seed = np.full(changed.shape, 255, np.uint8)
    rank = np.zeros(changed.shape, np.uint8)
    for e in timeline:
        if e['kind'] == 'draw':
            a, b = tuple(map(round, e['a'])), tuple(map(round, e['b']))
            cv2.line(seed, a, b, 0, 1)
            cv2.line(rank, a, b, max(1, round(e['end'] * 240)), 1)
    if np.any(seed == 0):
        _, labels = cv2.distanceTransformWithLabels(seed, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        values = np.concatenate([[0], rank[seed == 0]])
        ranks = values[labels].astype(np.uint8)
    else:
        yy, xx = np.indices(changed.shape)
        ranks = np.uint8((xx / changed.shape[1] + yy / changed.shape[0]) * 120)
    ranks[changed == 0] = 245
    return target, ranks, timeline, len(ordered)


def prepare_steps(source_folder, folder, config):
    raw = Image.open(original_path(source_folder)).convert('RGB')
    raw.save(folder / 'original.png')
    final_crop = config['stages'][-1]['crop']
    aspect = final_crop['width'] * raw.width / (final_crop['height'] * raw.height)
    width, height = (640, max(128, round(640/aspect))) if aspect >= 1 else (max(128, round(640*aspect)), 640)
    panels = []
    for stage in config['stages']:
        c = stage['crop']
        box = (round(c['x']*raw.width), round(c['y']*raw.height),
               round((c['x']+c['width'])*raw.width), round((c['y']+c['height'])*raw.height))
        crop = raw.crop(box)
        # Match panel extents; registration below corrects the remaining subject drift.
        resized = np.array(crop.resize((width, height), Image.Resampling.LANCZOS))
        # A single crop is a complete composition, never a set of panels to merge.
        panels.append(resized if len(config['stages']) == 1 else normalize_paper(resized))
    reference = panels[-1]
    previous = np.full((height, width, 3), PAPER, np.uint8)
    stages, cursor, strokes = [], 0., 0
    total = sum(stage['seconds'] for stage in config['stages'])
    for i, (panel, requested) in enumerate(zip(panels, config['stages'])):
        dx, dy, scale, confidence = alignment(panel, reference) if config['align'] and i < len(panels)-1 else (0., 0., 1., 1.)
        if len(panels) > 1:
            dx += requested['offset_x'] * width / 100
            dy += requested['offset_y'] * height / 100
            scale *= requested['scale']
        transform = np.array([[scale, 0, width/2*(1-scale)+dx], [0, scale, height/2*(1-scale)+dy]], np.float32)
        aligned = cv2.warpAffine(panel, transform, (width, height), borderValue=tuple(map(int, PAPER)))
        target = aligned
        regions = reading_regions(target) if len(panels) == 1 else [(0,0,width,height)]
        ranks = color_layers(target, regions)
        timeline, count = swept_scene(previous, target, regions, ranks)
        Image.fromarray(target).save(folder / f'step-{i}.png')
        Image.fromarray(ranks).save(folder / f'rank-{i}.png')
        end = cursor + requested['seconds'] / total
        stages.append({'label': requested['label'], 'start': cursor, 'end': end,
                       'image': f'step-{i}.png', 'rank': f'rank-{i}.png', 'timeline': timeline,
                       'alignment': {'x': round(dx, 1), 'y': round(dy, 1), 'scale': round(scale, 3), 'confidence': confidence}})
        previous, cursor, strokes = target, end, strokes + count
    stages[-1]['end'] = 1.
    Image.fromarray(previous).save(folder / 'source.png')
    Image.new('L', (width, height), 0).save(folder / 'reveal.png')
    scene = {'version': SCENE_VERSION, 'reveal_version': REVEAL_VERSION, 'mode': 'steps', 'width': width, 'height': height,
             'strokes': strokes, 'paths': [], 'timeline': [], 'stages': stages,
             'config': config, 'duration': total}
    (folder / 'scene.json').write_text(json.dumps(scene))
    return scene


def stage_at(scene, progress):
    index = next((i for i, stage in enumerate(scene['stages']) if progress < stage['end']), len(scene['stages'])-1)
    stage = scene['stages'][index]
    local = np.clip((progress-stage['start'])/(stage['end']-stage['start']), 0, 1)
    return index, float(local)


class StepFrames:
    def __init__(self, folder, scene):
        self.scene = scene
        self.targets = [np.array(Image.open(folder / stage['image']).convert('RGB')) for stage in scene['stages']]
        self.ranks = [np.array(Image.open(folder / stage['rank'])).astype(float) for stage in scene['stages']]
        self.paper = np.full_like(self.targets[0], PAPER)
        self.mask = np.zeros(self.paper.shape[:2], dtype=bool)
        self.index, self.amount, self.cursor = -1, -1., 0

    def sweep(self, event, fraction):
        a = np.array(event['a']); b = a+(np.array(event['b'])-a)*fraction
        cx0,cy0,cx1,cy1 = event['clip']
        x0,y0 = max(cx0, math.floor(min(a[0],b[0])-4)), max(cy0, math.floor(min(a[1],b[1])-4))
        x1,y1 = min(cx1, math.ceil(max(a[0],b[0])+4)+1), min(cy1, math.ceil(max(a[1],b[1])+4)+1)
        yy,xx = np.mgrid[y0:y1,x0:x1]
        delta = b-a
        t = np.clip(((xx-a[0])*delta[0]+(yy-a[1])*delta[1])/max(float(delta@delta),1e-12),0,1)
        swept = (xx-a[0]-t*delta[0])**2+(yy-a[1]-t*delta[1])**2 <= 16
        if 'color' in event:
            swept &= self.ranks[self.index][y0:y1,x0:x1] == event['color']
        self.mask[y0:y1,x0:x1] |= swept

    def frame(self, progress):
        index, local = stage_at(self.scene, progress)
        stage = self.scene['stages'][index]
        amount = min(1., local / .9)
        if self.scene.get('reveal_version', 0) >= 2:
            if index != self.index or amount < self.amount:
                self.mask.fill(False); self.cursor = 0
            self.index = index
            events = stage['timeline']
            while self.cursor < len(events):
                event = events[self.cursor]
                if event['start'] >= amount: break
                if event['kind'] == 'draw':
                    self.sweep(event, min(1., (amount-event['start'])/(event['end']-event['start'])))
                if event['end'] > amount: break
                self.cursor += 1
            self.index, self.amount = index, amount
            mask = self.mask[...,None]
        else:
            mask = np.clip((amount*270-self.ranks[index])/20, 0, 1)[..., None]
        previous = self.targets[index-1] if index else self.paper
        image = np.uint8(previous*(1-mask) + self.targets[index]*mask)
        tip, lift = None, 0
        if amount < 1:
            event = next((e for e in stage['timeline'] if e['end'] > amount), None)
            if event:
                tip, lift = event_position(event, (amount-event['start'])/(event['end']-event['start']))
        return image, tip, lift, f"Step {index+1}: {stage['label']}"
