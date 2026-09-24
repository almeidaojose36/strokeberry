#!/usr/bin/env node
/**
 * Renders the landing-page gallery with Strokeberry's own pipeline: uploads each
 * illustration from assets/gallery-src/ to the running API, exports a square
 * MP4, and saves it plus a finished-frame poster to frontend/public/gallery/.
 * Also writes scroll-draw.mp4, an all-keyframe copy used for scroll scrubbing.
 *
 *   npm run server   # in another terminal (or set STROKEBERRY_API)
 *   node scripts/render-gallery.mjs              # render everything
 *   node scripts/render-gallery.mjs strawberry   # render specific keys
 *
 * Requires ffmpeg on PATH (or FFMPEG_PATH) for posters and the scroll video.
 */
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const API = process.env.STROKEBERRY_API || "http://127.0.0.1:8001";
const SRC = path.join(root, "assets/gallery-src");
const OUT = path.join(root, "frontend/public/gallery");
const FFMPEG = process.env.FFMPEG_PATH || "ffmpeg";

const ITEMS = [
  { key: "cat", style: "pencil", duration: 10 },
  { key: "sneaker", style: "ink", duration: 10 },
  { key: "coffee", style: "ink", duration: 10 },
  { key: "wreath", style: "pencil", duration: 12 },
  { key: "balloon", style: "ink", duration: 10 },
  { key: "strawberry", steps: ["Body shape", "Leaves & headphones", "Face & details", "Color"], seconds: [3, 4, 5, 4],
    // Crops sit just inside the light-blue dividers (rows 477–479, columns 478–481 of 960).
    crops: [[0, 0], [486, 0], [0, 486], [486, 486]].map(([x, y]) => ({ x: x / 960, y: y / 960, width: 472 / 960, height: 472 / 960 })) },
  { key: "owl", steps: ["Guide shapes", "Outlines", "Details", "Color"], seconds: [3, 4, 4, 5] },
];
const SCROLL_KEY = "cat";

async function api(url, options) {
  const res = await fetch(API + url, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`${res.status} ${typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body)}`);
  return body;
}
const json = body => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function upload(file) {
  const form = new FormData();
  form.append("file", new Blob([await readFile(path.join(SRC, file))], { type: file.endsWith(".png") ? "image/png" : "image/jpeg" }), file);
  return api("/api/projects", { method: "POST", body: form });
}

async function render(item, manifest) {
  let project = await upload(manifest[item.key]);
  let duration = item.duration;
  if (item.steps) {
    let crops = item.crops;
    if (!crops) {
      const layout = await api(`/api/projects/${project.id}/step-layout`);
      if (!layout.detected || layout.crops.length !== item.steps.length)
        throw new Error(`expected ${item.steps.length} panels, found ${layout.crops.length}`);
      crops = layout.crops;
    }
    const stages = crops.map((crop, i) => ({ crop, label: item.steps[i], seconds: item.seconds[i] }));
    project = await api(`/api/projects/${project.id}/steps`, json({ stages, align: true }));
    duration = project.duration;
  }
  const settings = { style: item.style || "pencil", duration, ratio: "1:1", resolution: "720p", color: true, pen: true };
  let job = await api(`/api/projects/${project.id}/jobs`, json(settings));
  while (!["completed", "failed"].includes(job.status)) {
    await sleep(1500);
    job = await api(`/api/jobs/${job.id}`);
  }
  if (job.status === "failed") throw new Error(job.error);
  const video = path.join(OUT, `${item.key}.mp4`);
  await writeFile(video, Buffer.from(await (await fetch(API + job.url)).arrayBuffer()));
  execFileSync(FFMPEG, ["-loglevel", "error", "-y", "-sseof", "-0.2", "-i", video, "-frames:v", "1", "-q:v", "3", path.join(OUT, `${item.key}.jpg`)]);
  return { key: item.key, style: item.steps ? "steps" : settings.style, duration };
}

await mkdir(OUT, { recursive: true });
const manifest = JSON.parse(await readFile(path.join(SRC, "manifest.json"), "utf8"));
const wanted = process.argv.slice(2);
const galleryPath = path.join(OUT, "gallery.json");
const previous = wanted.length ? JSON.parse(await readFile(galleryPath, "utf8").catch(() => "[]")) : [];
const results = previous.filter(r => !wanted.includes(r.key));
for (const item of ITEMS.filter(i => !wanted.length || wanted.includes(i.key))) {
  process.stdout.write(`→ ${item.key} … `);
  try {
    results.push(await render(item, manifest));
    console.log("done");
  } catch (e) {
    console.log(`failed: ${e.message}`);
  }
}
// Every frame a keyframe so the browser can seek smoothly while scrolling.
if (!wanted.length || wanted.includes(SCROLL_KEY)) execFileSync(FFMPEG, ["-loglevel", "error", "-y", "-i", path.join(OUT, `${SCROLL_KEY}.mp4`), "-vf", "scale=540:540",
  "-c:v", "libx264", "-g", "1", "-crf", "28", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", path.join(OUT, "scroll-draw.mp4")]);
await writeFile(galleryPath, JSON.stringify(results, null, 2) + "\n");
console.log(`gallery.json now lists ${results.length} videos in frontend/public/gallery/`);
