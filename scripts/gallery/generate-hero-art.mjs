#!/usr/bin/env node
/**
 * Generates the source illustrations for the landing-page hero clips with KIE (grok-imagine-image-2-0), one subject per
 * audience Strokeberry is for, two candidates each. Marketing art only (user uploads never go to KIE); the chosen images
 * are then drawn by Strokeberry itself (scripts/gallery/render_hero.py), so the hero shows real output.
 *
 *   node scripts/gallery/generate-hero-art.mjs [key ...]
 *   node scripts/gallery/generate-hero-art.mjs --set interiors --model z-image [key ...]
 *
 * Writes assets/hero-src/<key>-1.jpg and -2.jpg (assets/interiors-src/ for --set interiors, assets/sports-src/ for --set sports). --model picks another
 * KIE model: z-image is the cheapest (0.8 credits an image, October 2026). KIE_API_KEY is read from .env.local.
 */
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const arg = name => { const i = process.argv.indexOf(name); return i > 0 ? process.argv.splice(i, 2)[1] : null; };
const SET = arg("--set") || "hero";
const OUT = path.join(root, { interiors: "assets/interiors-src", sports: "assets/sports-src" }[SET] || "assets/hero-src");
const KIE_API = "https://api.kie.ai/api/v1/jobs";
const MODEL = arg("--model") || "grok-imagine-image-2-0/text-to-image";
// Sports art is briefed like a children's drawing book: thick black outlines around every shape, flat colour fills.
const SPORTS_STYLE =
  "Drawing-book illustration, like a page from a kids' how-to-draw book: thick, clean, uniform black outlines around every shape and every detail, flat solid colour fills inside the outlines, no shading. Pure white background, subject centered with generous margins. No text, no letters, no numbers, no logos, no brand names, no watermark, no border frame, no signature.";
const STYLE =
  "Clean vector-style illustration with bold, smooth black outlines and flat solid colors. Pure white background, subject centered with generous margins. No shading gradients, no texture, no text, no letters, no numbers, no logos, no brand names, no watermark, no border, no signature.";

export const JOBS = [  // audience: subject
  { key: "skincare", prompt: "E-commerce product illustration: an elegant glass skincare serum bottle with a dropper cap, next to a small cream jar, surrounded by a few green botanical leaves and a slice of lemon. Soft blush pink, sage green and gold accents." },
  { key: "fashion", prompt: "Fashion illustration: a structured leather handbag with a gold clasp beside a pair of pointed high-heel shoes, one standing and one lying on its side. Terracotta, cream and black with gold accents." },
  { key: "cafe", prompt: "A round coffee-shop badge emblem: a steaming coffee cup with a heart of latte art in the centre, framed by a laurel of coffee leaves and two coffee beans. Warm brown, caramel and cream. No words on the badge." },
  { key: "creator", prompt: "Content creator setup: a smartphone mounted on a small tripod with a round ring light behind it, a clip-on microphone beside it and three floating speech-bubble icons with a heart, a thumbs-up and a star. Coral, teal and warm grey. Nothing that looks like a real app or platform logo." },
  { key: "lesson", prompt: "Education illustration: an open book with a small cartoon rocket launching out of its pages, surrounded by two little planets, a star and a pencil. Bright blue, orange and yellow." },
  { key: "house", prompt: "Real estate illustration: a modern two-storey house with a pitched roof, large windows, a front door with a small porch, a round tree and a little garden path. Sage green, warm white walls, wood and terracotta." },
];

// Floor plans, interior design and furniture brands (a possible new audience; tested before being promised anywhere).
export const INTERIORS = [
  { key: "floorplan", prompt: "Architectural floor plan of a small two-bedroom apartment seen from directly above, drawn like a bold illustration: black outer walls, inner walls and door swing arcs, and every piece of furniture (a sofa, two beds with pillows, a dining table with four chairs, a kitchen counter with a sink, a bathtub and plants) drawn with the same bold black outline as the walls. Soft beige floors, light wood and sage green furniture. No text, no labels, no dimensions, no numbers." },
  { key: "livingroom", prompt: "Interior design illustration of a cosy Scandinavian living room: a three-seat sofa with cushions, a round wooden coffee table, a floor lamp, a large potted plant, a framed abstract picture on the wall and a patterned rug. Warm beige, sage green, terracotta and light oak." },
  { key: "armchair", prompt: "Furniture product illustration: a mid-century modern lounge armchair with curved wooden arms, tapered legs and a mustard yellow upholstered seat and back, with a small round side table beside it. Mustard, walnut wood and warm grey." },
  { key: "kitchen", prompt: "Interior design illustration of a modern kitchen: shaker-style cabinets, an island with two bar stools, pendant lights above, open shelves with plates and jars, a window and a plant. Sage green cabinets, white worktops, light oak and brass accents." },
];

// Invented athletes in plain flag-coloured kits: no real people, no federation crests, no sponsor or brand marks.
export const SPORTS = [
  { key: "striker", prompt: "Illustration of an invented football (soccer) striker celebrating a goal, running with arms spread and mouth open in a shout. A detailed, well-drawn face with two eyes, nose, mouth and short dark hair, correct human anatomy with exactly two arms and two legs. He wears a plain Portugal-flag kit: a deep red shirt with a green sleeve and green collar trim, red shorts and green socks, in the colours of the Portuguese flag. No badge, no crest, no logo, no number, no text." },
  { key: "keeper", prompt: "Illustration of an invented football (soccer) goalkeeper diving to his left with both gloved hands stretched towards a ball. A detailed, well-drawn face with two eyes, nose, mouth and short dark hair, correct human anatomy with exactly two arms and two legs. He wears a plain Argentina-flag kit: a shirt with sky blue and white vertical stripes, sky blue shorts, white socks and neon yellow gloves. No badge, no crest, no logo, no number, no text." },
  { key: "sprinter", prompt: "Illustration of an invented African American female sprinter running at full speed on a track, leaning forward, side view. A detailed, well-drawn face in profile with a focused expression, dark brown skin, hair tied back, correct human anatomy with exactly two arms and two legs and both feet in running spikes. She wears a plain United States-flag kit: a white crop top with red and blue stripes across the chest and blue shorts with white stars, in the colours of the American flag. No logo, no number, no text." },
  { key: "boxer", prompt: "Illustration of an invented boxer in a guard stance, facing the viewer, with a determined expression. A detailed, well-drawn face with two eyes, nose, mouth and short hair, correct human anatomy with exactly two arms and two legs. He wears red boxing gloves and plain France-flag trunks of blue, white and red vertical bands. No logo, no text." },
  { key: "dunk", prompt: "Illustration of an invented African American basketball player in mid-air making a one-handed dunk, shown with correct human anatomy: exactly two arms and exactly two legs, both legs clearly visible and both feet in sneakers. A detailed, well-drawn face with two eyes, nose and mouth, dark brown skin, short hair. He wears a plain Spain-flag kit: a red basketball jersey and shorts with yellow trim, in the colours of the Spanish flag. A hoop and backboard at the top. No logo, no number, no text." },
  { key: "rugby", prompt: "Illustration of an invented rugby player running with the ball held in both hands, powerful build. A detailed, well-drawn face with two eyes, nose, mouth and short hair, correct human anatomy with exactly two arms and two legs. He wears a plain Ireland-flag kit: a green jersey with white and orange trim, green shorts and socks, in the colours of the Irish flag. No badge, no logo, no number, no text." },
  { key: "cricketer", prompt: "Illustration of an invented cricket batter in mid-swing, bat raised, wearing a helmet with the face visible. A detailed, well-drawn face with two eyes, nose and mouth, correct human anatomy with exactly two arms and two legs. He wears a plain India-flag kit: a saffron orange and white shirt with a green trim, white trousers and pads, in the colours of the Indian flag. No logo, no number, no text." },
  { key: "fan", prompt: "Illustration of an invented football fan cheering with arms raised, a joyful detailed face with two eyes, nose and open smiling mouth, correct human anatomy with exactly two arms. Face painted with stripes of green, yellow and blue, a scarf in the same colours, holding up a large plain Brazil-style flag of a green field, yellow diamond and blue circle with no text. No logo." },
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
  const res = await fetch(url, { method, headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || (json.code && json.code !== 200)) throw new Error(`${json.code ?? res.status} ${json.msg ?? res.statusText}`);
  return json.data;
}
async function generate(job, n, key) {
  const { taskId } = await kie("POST", `${KIE_API}/createTask`, key, { model: MODEL, input: { prompt: `${job.prompt} ${SET === "sports" ? SPORTS_STYLE : STYLE}`, aspect_ratio: "1:1" } });
  const deadline = Date.now() + 6 * 60_000;
  while (Date.now() < deadline) {
    await sleep(4000);
    const t = await kie("GET", `${KIE_API}/recordInfo?taskId=${encodeURIComponent(taskId)}`, key);
    if (t.state === "success") {
      const url = JSON.parse(t.resultJson || "{}").resultUrls?.[0];
      const file = path.join(OUT, `${job.key}-${n}.jpg`);
      await writeFile(file, Buffer.from(await (await fetch(url)).arrayBuffer()));
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
const wanted = process.argv.slice(2);
const jobs = ({ interiors: INTERIORS, sports: SPORTS }[SET] || JOBS).filter(j => !wanted.length || wanted.includes(j.key));
await Promise.all(jobs.flatMap(job => [1, 2].map(n => generate(job, n, key)
  .then(f => console.log("  " + path.relative(root, f)), e => console.error(`  ${job.key} #${n}: ${e.message}`)))));
