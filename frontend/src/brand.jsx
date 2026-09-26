import React from 'react';

// Change the product name in one place.
export const BRAND = {name: 'Strokeberry', tagline: 'Your images. Drawn to life.'};

// The Strokeberry mark: the strawberry mascot in headphones, pencil in hand.
// Approved artwork; PNGs are exported by scripts/brand/export.py (full mascot: strokeberry-mascot.png).
// Brand rule: the full mascot everywhere; the compact logo only at small sizes (under ~48 px, e.g. avatars, favicons).
export function BrandMark({size = 40, compact = false}) {
  if (compact) return <img className="brand-mark" src="/brand/strokeberry-icon-512.png" width={size} height={size} alt="" />;
  return <img className="brand-mark" src="/brand/strokeberry-mascot.png" srcSet="/brand/strokeberry-mascot@2x.png 2x" width={Math.round(size * .967)} height={size} alt="" />;
}
