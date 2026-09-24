#!/usr/bin/env node
/**
 * Generates original line-art illustrations for the landing-page gallery with
 * KIE (grok-imagine-image-2-0/text-to-image). These are marketing assets only;
 * user uploads are never sent to KIE. The images are then drawn by Strokeberry
 * itself (see scripts/render-gallery.mjs) so the gallery shows real output.
 *
 *   node scripts/generate-gallery.mjs            # generate missing images
 *   node scripts/generate-gallery.mjs cat owl    # (re)generate specific keys
 *
 * KIE_API_KEY is read from .env.local and never reaches the browser bundle.
 */
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(root, "assets/gallery-src");
const KIE_API = "https://api.kie.ai/api/v1/jobs";
const MODEL = "grok-imagine-image-2-0/text-to-image";
const STYLE =
  "Clean vector-style illustration with bold, smooth black outlines and flat solid colors. Pure white background, subject centered with generous margins. No shading gradients, no texture, no text, no letters, no numbers, no watermark, no border, no signature.";

export const JOBS = [
  { key: "cat", prompt: "A cute round cat sitting and curling its tail, big eyes, orange and cream fur." },
  { key: "sneaker", prompt: "A single modern high-top sneaker in side view, red, white and teal color blocks, laces and sole details." },
  { key: "coffee", prompt: "A takeaway coffee cup with a cardboard sleeve and three curly steam lines, next to a croissant." },
  { key: "wreath", prompt: "A round botanical wreath of leaves, small berries and three blooming flowers, in greens, coral and yellow." },
  { key: "balloon", prompt: "A striped hot-air balloon with a wicker basket floating above two rounded hills and a small cloud." },
  { key: "strawberry", prompt: "A how-to-draw tutorial sheet for kids arranged as a 2 by 2 grid of four equal square panels, separated by thin light-blue divider lines, showing the same original cute cartoon strawberry character wearing over-ear headphones at four stages, same size and position in every panel: panel 1 only the simple rounded heart-like strawberry body outline; panel 2 adds the leafy green crown on top and the headphone band and ear cups as outlines; panel 3 adds big friendly eyes, a smile, rosy cheeks, seed dots and small details, still black and white line art; panel 4 the finished character fully colored in bright red with yellow seeds, green leaves and teal headphones with a coral accent." },
  { key: "owl", prompt: "A how-to-draw tutorial sheet arranged as a 2 by 2 grid of four equal square panels on white, each panel separated by white space, showing the same cute owl at four stages: panel 1 only light gray basic circles and guide lines; panel 2 clean black outlines of the owl; panel 3 outlines plus feather details, eyes and branch; panel 4 the finished owl colored in brown, cream and orange. Same size and position of the owl in every panel." },
];

async function loadEnv() {
  const f = path.join(root, ".env.local");
  if (!existsSync(f)) return;
  for (const line of (await readFile(f, "utf8")).split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function kie(method, url, key, body) {
  const res = await fetch(url, {
    method,
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || (json.code && json.code !== 200)) throw new Error(`${json.code ?? res.status} ${json.msg ?? res.statusText}`);
  return json.data;
}

async function generate(job, key) {
  const { taskId } = await kie("POST", `${KIE_API}/createTask`, key, {
    model: MODEL,
    input: { prompt: `${job.prompt} ${STYLE}`, aspect_ratio: "1:1" },
  });
  console.log(`  queued ${job.key} (${taskId})`);
  let wait = 3000;
  const deadline = Date.now() + 5 * 60_000;
  for (;;) {
    await sleep(wait);
    const t = await kie("GET", `${KIE_API}/recordInfo?taskId=${encodeURIComponent(taskId)}`, key);
    if (t.state === "success") {
      const url = JSON.parse(t.resultJson || "{}").resultUrls?.[0];
      if (!url) throw new Error("KIE returned no result URL");
      const res = await fetch(url);
      const type = res.headers.get("content-type") || "";
      const file = `${job.key}.${type.includes("png") ? "png" : type.includes("webp") ? "webp" : "jpg"}`;
      await writeFile(path.join(OUT, file), Buffer.from(await res.arrayBuffer()));
      return file;
    }
    if (t.state === "fail") throw new Error(`${t.failCode}: ${t.failMsg}`);
    if (Date.now() > deadline) throw new Error("timed out waiting for KIE");
    wait = Math.min(wait * 1.5, 20_000);
  }
}

await loadEnv();
const key = process.env.KIE_API_KEY;
if (!key) {
  console.error("Missing KIE_API_KEY — add it to .env.local");
  process.exit(1);
}
await mkdir(OUT, { recursive: true });
const manifestPath = path.join(OUT, "manifest.json");
const manifest = existsSync(manifestPath) ? JSON.parse(await readFile(manifestPath, "utf8")) : {};
const wanted = process.argv.slice(2);
const jobs = JOBS.filter(j => (wanted.length ? wanted.includes(j.key) : !manifest[j.key]));
if (!jobs.length) console.log("Nothing to generate.");

let failed = 0;
for (const job of jobs) {
  console.log(`→ ${job.key}`);
  try {
    manifest[job.key] = await generate(job, key);
    await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
    console.log(`  saved assets/gallery-src/${manifest[job.key]}`);
  } catch (e) {
    failed++;
    console.error(`  ✗ ${job.key}: ${e.message}`);
    if (/^(401|402)\b/.test(e.message)) {
      console.error("\nStopping: KIE rejected the key or the account is out of credits.");
      process.exit(1);
    }
  }
}
process.exit(failed ? 1 : 0);
