#!/usr/bin/env node
/**
 * Generates a made-up demo brand logo for the tutorial videos with KIE (grok-imagine-image-2-0).
 * The brand is fictional, so the videos never feature a real company's trademark.
 *
 *   node scripts/tutorials/generate-demo-logo.mjs [count]
 *
 * Writes marketing/demo-brands/little-crumb/logo-N.(png|jpg). KIE_API_KEY is read from .env.local.
 */
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = path.join(root, "marketing/demo-brands/little-crumb");
const KIE_API = "https://api.kie.ai/api/v1/jobs";
const MODEL = "grok-imagine-image-2-0/text-to-image";
const PROMPT =
  "A professional logo for a small independent coffee shop called \"Little Crumb Coffee Co.\". " +
  "A round badge emblem: in the centre a simple takeaway coffee cup with two curly steam lines and a small croissant beside it, " +
  "the name \"LITTLE CRUMB\" in bold rounded capital letters arched along the top of the circle and \"COFFEE CO.\" along the bottom, " +
  "two small stars between the words. Clean flat vector line-art logo with bold, smooth dark brown outlines and flat fills in warm caramel, " +
  "cream and soft terracotta. Spelling exactly as written. Pure white background, logo centred with generous margins. " +
  "No gradients, no texture, no shadow, no mockup, no photo, no extra text, no watermark.";

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
async function generate(n, key) {
  const { taskId } = await kie("POST", `${KIE_API}/createTask`, key, { model: MODEL, input: { prompt: PROMPT, aspect_ratio: "1:1" } });
  const deadline = Date.now() + 5 * 60_000;
  while (Date.now() < deadline) {
    await sleep(4000);
    const t = await kie("GET", `${KIE_API}/recordInfo?taskId=${encodeURIComponent(taskId)}`, key);
    if (t.state === "success") {
      const url = JSON.parse(t.resultJson || "{}").resultUrls?.[0];
      const res = await fetch(url);
      const type = res.headers.get("content-type") || "";
      const file = path.join(OUT, `logo-${n}.${type.includes("png") ? "png" : "jpg"}`);
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
const count = Number(process.argv[2] || 2);
const files = await Promise.all(Array.from({ length: count }, (_, i) => generate(i + 1, key)));
files.forEach(f => console.log("  " + path.relative(root, f)));
