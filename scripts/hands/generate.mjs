#!/usr/bin/env node
/**
 * Generates the realistic drawing-hand artwork with KIE (grok-imagine-image-2-0): a right hand holding a pencil or an ink pen
 * (line phase, for the Pencil and Ink styles) or a brush (colour phase) in three skin tones, two candidates each.
 *
 *   node scripts/hands/generate.mjs [tone/tool ...]     e.g. light/pencil dark/brush   (default: all nine)
 *
 * Writes marketing/hands/<tone>-<tool>-<n>.(png|jpg). Cut-outs for the app are made by scripts/hands/cutout.py.
 * KIE_API_KEY is read from .env.local.
 */
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = path.join(root, "marketing/hands");
const KIE_API = "https://api.kie.ai/api/v1/jobs";
const MODEL = "grok-imagine-image-2-0/text-to-image";
const TONES = { light: "fair, light", medium: "medium olive-tan", dark: "deep dark brown" };
const TOOLS = {
  pencil: "a sharpened yellow wooden pencil, held as if drawing",
  pen: "a slim black fine-liner ink pen with a matte black barrel and a fine black tip, held as if drawing",
  brush: "a slim artist's paintbrush with a wooden handle and a small round tip wet with paint, held as if painting",
};
const prompt = (tone, tool) =>
  `Photorealistic close-up of a human right hand with ${TONES[tone]} skin holding ${TOOLS[tool]}. ` +
  "Seen from above at a slight angle, like an artist drawing on a sheet of paper lying flat. " +
  "The tip points down towards the lower left of the image and is clearly visible and sharp. " +
  "The bare forearm comes in from the bottom right corner of the image and is cut off by the image edge. " +
  "No sleeve, no jewelry, no nail polish, relaxed natural grip, soft even studio lighting. " +
  "Isolated on a pure flat white background: no paper, no table, no shadow, no drawing, no text, nothing else in the image.";

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
  const res = await fetch(url, { method, headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || (json.code && json.code !== 200)) throw new Error(`${json.code ?? res.status} ${json.msg ?? res.statusText}`);
  return json.data;
}
async function generate(tone, tool, n, key) {
  const { taskId } = await kie("POST", `${KIE_API}/createTask`, key, { model: MODEL, input: { prompt: prompt(tone, tool), aspect_ratio: "1:1" } });
  const deadline = Date.now() + 6 * 60_000;
  while (Date.now() < deadline) {
    await sleep(4000);
    const t = await kie("GET", `${KIE_API}/recordInfo?taskId=${encodeURIComponent(taskId)}`, key);
    if (t.state === "success") {
      const url = JSON.parse(t.resultJson || "{}").resultUrls?.[0];
      const res = await fetch(url);
      const type = res.headers.get("content-type") || "";
      const file = path.join(OUT, `${tone}-${tool}-${n}.${type.includes("png") ? "png" : "jpg"}`);
      await writeFile(file, Buffer.from(await res.arrayBuffer()));
      return file;
    }
    if (t.state === "fail") throw new Error(t.failMsg || "KIE task failed");
  }
  throw new Error("KIE timed out");
}

await loadEnv();
const key = process.env.KIE_API_KEY;
if (!key) throw new Error("KIE_API_KEY missing (.env.local)");
await mkdir(OUT, { recursive: true });
const wanted = process.argv.slice(2).length ? process.argv.slice(2)
  : Object.keys(TONES).flatMap(tone => Object.keys(TOOLS).map(tool => `${tone}/${tool}`));
const jobs = wanted.flatMap(w => { const [tone, tool] = w.split("/"); return [1, 2].map(n => generate(tone, tool, n, key)
  .then(f => console.log("  " + path.relative(root, f)), e => console.error(`  ${w} #${n}: ${e.message}`))); });
await Promise.all(jobs);
