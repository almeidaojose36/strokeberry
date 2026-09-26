#!/usr/bin/env python3
"""Cuts the approved compact Strokeberry mark out of the approval sheet (the 03 app icon)
and saves it with a transparent background to marketing/brand-sources/approved/compact-mark.png."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "marketing/brand-sources/approved"

sheet = Image.open(SRC / "approval-sheet.webp").convert("RGB")
card = sheet.crop((1240, 578, 1552, 890)).resize((1248, 1248), Image.LANCZOS)
rgb = np.asarray(card).astype(int)
near_cream = (np.sqrt(((rgb - [253, 247, 235]) ** 2).sum(-1)) < 45).astype(np.uint8)
# The background is the cream region connected to a point in the card's corner.
_, labels = cv2.connectedComponents(near_cream, connectivity=4)
background = labels == labels[160, 160]
# Keep only the artwork (the piece touching the centre), dropping stray bits of the card's shadow.
_, parts = cv2.connectedComponents((~background).astype(np.uint8), connectivity=8)
background = parts != parts[624, 624]
alpha = Image.fromarray(np.where(background, 0, 255).astype(np.uint8))
alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
mark = card.convert("RGBA")
mark.putalpha(alpha)
mark = mark.crop(alpha.point(lambda v: 255 if v > 8 else 0).getbbox())
side = max(mark.size) + 40
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(mark, ((side - mark.width) // 2, (side - mark.height) // 2))
square.save(SRC / "compact-mark.png")
print("compact-mark.png", square.size)
