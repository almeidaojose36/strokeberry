"""Cut the generated hand photos out of their white background for the app.

    .venv/bin/python scripts/hands/cutout.py light-pencil-2 medium-pencil-1 ...   (the chosen candidates)

For each marketing/hands/<tone>-<tool>-<n>.jpg it writes frontend/public/hands/<tone>-<tool>.png (transparent, with a soft
drop shadow so the hand sits on the page) and records in frontend/public/hands/hands.json where the tip of the pencil or
brush is, as a share of the image size; the renderer puts that point exactly on the line being drawn.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC, OUT = ROOT / 'marketing' / 'hands', ROOT / 'frontend' / 'public' / 'hands'
SIZE = 900  # longest side of the saved cut-out


def extend_arm(rgb, alpha):
    """The photo's forearm stops at the image edge, which shows as a straight cut whenever the hand is drawing near the
    middle of a frame. Continue the forearm along its own direction (repeating the slice at the edge) so it always runs
    off the frame. Returns the larger image, its alpha, and the share of the new height that the original photo takes."""
    h, w = alpha.shape
    solid = alpha > .5
    yy, xx = np.nonzero(solid)
    edge_gap = np.minimum(w - 1 - xx, h - 1 - yy)                    # distance to the right or bottom edge
    near, far = edge_gap < 30, (edge_gap > 140) & (edge_gap < 200)
    if near.sum() < 50 or far.sum() < 50:
        return rgb, alpha, h
    direction = np.array([xx[near].mean() - xx[far].mean(), yy[near].mean() - yy[far].mean()])
    direction /= np.linalg.norm(direction) + 1e-6
    pad = int(max(h, w) * 1.1)
    big_rgb = np.zeros((h + pad, w + pad, 3), np.float32)
    big_alpha = np.zeros((h + pad, w + pad), np.float32)
    big_rgb[:h, :w], big_alpha[:h, :w] = rgb, alpha
    slice_y, slice_x = yy[near], xx[near]
    colours, weights = rgb[slice_y, slice_x].astype(np.float32), alpha[slice_y, slice_x]
    for step in range(3, pad, 3):
        ty = np.round(slice_y + direction[1] * step).astype(int)
        tx = np.round(slice_x + direction[0] * step).astype(int)
        keep = (ty < h + pad) & (tx < w + pad) & (ty >= 0) & (tx >= 0)
        ty, tx = ty[keep], tx[keep]
        empty = big_alpha[ty, tx] < weights[keep]
        big_rgb[ty[empty], tx[empty]] = colours[keep][empty]
        big_alpha[ty[empty], tx[empty]] = weights[keep][empty]
    big_alpha = cv2.morphologyEx(big_alpha, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))  # fill the gaps between steps
    big_rgb = np.where(big_alpha[..., None] > 0, cv2.dilate(big_rgb, np.ones((3, 3), np.uint8)) * (big_rgb.sum(axis=2, keepdims=True) == 0)
                       + big_rgb, big_rgb)
    added = np.ones(big_alpha.shape, bool)
    added[:h, :w] = alpha <= .5                                      # only pixels the photo didn't already have
    smooth = cv2.GaussianBlur(big_rgb, (0, 0), 6)
    big_rgb = np.where(added[..., None] & (big_alpha[..., None] > 0), smooth, big_rgb)  # soften the repeated slice
    ys, xs = np.nonzero(big_alpha > .02)
    bottom, right = int(ys.max()) + 1, int(xs.max()) + 1
    return big_rgb[:bottom, :right].astype(np.uint8), big_alpha[:bottom, :right], h


def cutout(path):
    rgb = np.array(Image.open(path).convert('RGB'))
    darkness = 255 - rgb.min(axis=2).astype(np.int16)                 # 0 on pure white
    spread = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2)
    whiteish = np.uint8((darkness < 120) & (spread < 14))  # white and the soft grey shadows on it; skin is always tinted
    count, labels = cv2.connectedComponents(whiteish)
    edge = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    background = np.isin(labels, edge[edge > 0])                    # only the white that touches the border
    near = cv2.dilate(np.uint8(background), np.ones((5, 5), np.uint8)) > 0
    # Refine with GrabCut: it learns the skin and the background colours, which separates the soft shadow the photo casts
    # beside the arm (tinted by the skin, so a colour threshold alone keeps it as a pale fringe).
    sure_bg = np.isin(labels, edge[edge > 0]) & (darkness < 22)
    mask = np.full(background.shape, cv2.GC_PR_FGD, np.uint8)
    mask[background] = cv2.GC_PR_BGD
    mask[sure_bg] = cv2.GC_BGD
    mask[cv2.erode(np.uint8(~background), np.ones((25, 25), np.uint8)) > 0] = cv2.GC_FGD
    small = 2 if max(rgb.shape) > 1000 else 1
    work = cv2.resize(mask, None, fx=1 / small, fy=1 / small, interpolation=cv2.INTER_NEAREST)
    image_small = cv2.resize(rgb, (work.shape[1], work.shape[0]), interpolation=cv2.INTER_AREA)
    cv2.grabCut(cv2.cvtColor(image_small, cv2.COLOR_RGB2BGR), work, None, np.zeros((1, 65), np.float64),
                np.zeros((1, 65), np.float64), 4, cv2.GC_INIT_WITH_MASK)
    work = cv2.resize(work, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
    background = (work == cv2.GC_BGD) | (work == cv2.GC_PR_BGD)
    near = cv2.dilate(np.uint8(background), np.ones((5, 5), np.uint8)) > 0
    alpha = np.where(background, 0., 1.)
    soft = np.clip((darkness - 6) / 16, 0, 1)                         # anti-aliased rim where the hand meets the white
    alpha = cv2.GaussianBlur(alpha.astype(np.float32), (5, 5), 0)  # a soft, anti-aliased rim
    # The tip is the left-most solid point (the pencil or brush always points to the lower left).
    solid = alpha > .6
    count, labels, stats, _ = cv2.connectedComponentsWithStats(np.uint8(solid), 8)
    keep = labels == (1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA])))
    alpha *= cv2.dilate(np.uint8(keep), np.ones((7, 7), np.uint8)) > 0  # drop stray specks
    ys, xs = np.where(keep)
    tip = (int(xs.min()), int(np.median(ys[xs <= xs.min() + 2])))
    rgb, alpha, photo_h = extend_arm(rgb, alpha)
    # A soft shadow below and to the right, as if the hand hovered just above the page.
    h, w = alpha.shape
    shadow = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), w * .012)
    shift = int(w * .018)
    moved = np.zeros_like(shadow)
    moved[shift:, shift:] = shadow[:-shift, :-shift]                   # shifted, not wrapped round the edges
    shadow = moved * .28
    out_alpha = alpha + shadow * (1 - alpha)
    color = (rgb.astype(np.float32) * alpha[..., None]) / np.maximum(out_alpha[..., None], 1e-6)  # shadow is black
    rgba = np.dstack([np.clip(color, 0, 255), out_alpha * 255]).astype(np.uint8)
    ys, xs = np.where(out_alpha > .02)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    image = Image.fromarray(rgba).crop(box)
    tip = (tip[0] - box[0], tip[1] - box[1])
    factor = SIZE / max(image.size)
    image = image.resize((round(image.width * factor), round(image.height * factor)), Image.LANCZOS)
    hand = (min(photo_h, box[3]) - box[1]) / (box[3] - box[1])          # the share of the height that is the hand itself
    return image, (round(tip[0] / image.width * factor, 4), round(tip[1] / image.height * factor, 4)), round(hand, 4)


def main(names):
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / 'hands.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name in names:
        source = next(SRC.glob(f'{name}.*'))
        key = name.rsplit('-', 1)[0]                                    # light-pencil-2 -> light-pencil
        image, tip, hand_height = cutout(source)
        image.save(OUT / f'{key}.png', optimize=True)
        # `hand`: the share of the image height taken by the hand itself (the rest is the extended forearm).
        manifest[key] = {'file': f'{key}.png', 'tip': tip, 'aspect': round(image.width / image.height, 4), 'hand': hand_height}
        print(f'{key}: tip at {tip}, {image.size[0]}x{image.size[1]}')
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
