// Shared with backend/pipeline.py so the live preview matches the exported MP4: frame shapes, chalkboard canvases,
// the brush path the painting hand follows, and the realistic hand artwork.
export const PAPER = [250, 249, 246];
export const BOARDS = {blackboard: [40, 44, 42], greenboard: [38, 76, 60]};
export const CHALK = [240, 240, 232];
export const HAND_TONES = ['light', 'medium', 'dark'];

// Preview size for a format (the export uses the same shape at its own resolution).
export function frameSize(ratio, project, short = 540) {
  const even = value => Math.max(2, Math.round(value / 2) * 2);
  if (ratio === 'auto') {
    const aspect = Math.min(16 / 9, Math.max(9 / 16, project ? project.width / project.height : 16 / 9));
    return aspect >= 1 ? [even(short * aspect), short] : [short, even(short / aspect)];
  }
  if (ratio === '1:1') return [short, short];
  if (ratio === '4:5') return [short, even(short * 5 / 4)];
  if (ratio === '9:16') return [short, even(short * 16 / 9)];
  return [even(short * 16 / 9), short];
}

// Where the brush is at this point of the colour reveal (0..1), in source pixels.
export function paintPoint(path, amount) {
  if (!path?.length) return null;
  const t = Math.min(path.length - 1, Math.max(0, amount * path.length - .5)), i = Math.floor(t), j = Math.min(path.length - 1, i + 1), f = t - i;
  return [path[i][0] + (path[j][0] - path[i][0]) * f, path[i][1] + (path[j][1] - path[i][1]) * f];
}

// Pen-black pixels (dark and not strongly coloured), as in backend/linework.ink_mask.
function isInk(r, g, b) {
  const gray = .299 * r + .587 * g + .114 * b;
  return gray < 125 && Math.max(r, g, b) - Math.min(r, g, b) < 80;
}

// On a chalkboard: the picture's paper-coloured background becomes the board and its black outlines are never painted
// over the chalk lines. Returns the adjusted source pixels and a 0..1 "may reveal" weight per pixel.
export function boardSource(pixels, width, height, board) {
  const data = new Uint8ClampedArray(pixels), keep = new Float32Array(width * height);
  for (let p = 0, i = 0; p < keep.length; p++, i += 4) {
    const [r, g, b] = [data[i], data[i + 1], data[i + 2]];
    keep[p] = isInk(r, g, b) ? 0 : 1;
    const close = Math.max(0, Math.min(1, 1 - (Math.abs(r - PAPER[0]) + Math.abs(g - PAPER[1]) + Math.abs(b - PAPER[2])) / 24));
    for (let k = 0; k < 3; k++) data[i + k] = data[i + k] * (1 - close) + board[k] * close;
  }
  // soften the chalk mask a little, like the renderer's blur
  const soft = new Float32Array(keep.length);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    let sum = 0, n = 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const yy = y + dy, xx = x + dx;
      if (yy >= 0 && yy < height && xx >= 0 && xx < width) { sum += keep[yy * width + xx]; n++; }
    }
    soft[y * width + x] = sum / n;
  }
  return {data, keep: soft};
}

let handsManifest = null;
const handImages = {};
export function loadHands() {
  if (!handsManifest) handsManifest = fetch('/hands/hands.json').then(r => r.ok ? r.json() : {}).catch(() => ({}));
  return handsManifest;
}
// The hand image for a tone and tool, loading it on first use (falls back to the pencil hand of that tone).
export async function handArt(tone, tool) {
  const manifest = await loadHands();
  const key = manifest[`${tone}-${tool}`] ? `${tone}-${tool}` : manifest[`${tone}-pencil`] ? `${tone}-pencil` : null;
  if (!key) return null;
  if (!handImages[key]) handImages[key] = new Promise(resolve => {
    const img = new Image();
    img.onload = () => resolve({img, tip: manifest[key].tip, hand: manifest[key].hand || 1});
    img.onerror = () => resolve(null);
    img.src = `/hands/${manifest[key].file}`;
  });
  return handImages[key];
}

// Draw a loaded hand so its tip sits on (x, y) in canvas pixels; `frameShort` is the frame's shorter side.
export function drawHand(ctx, art, x, y, frameShort, lift = 0) {
  if (!art) return;
  const h = frameShort * .62 / art.hand, w = h * art.img.width / art.img.height, unit = frameShort / 540;
  ctx.drawImage(art.img, x - art.tip[0] * w + lift * 3 * unit, y - art.tip[1] * h - lift * 12 * unit, w, h);
}
