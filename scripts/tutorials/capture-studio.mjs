#!/usr/bin/env node
// Drives the real Strokeberry studio at phone size and captures each tutorial step as a 3x screenshot,
// plus the rectangle of every control that gets tapped (for tap highlights in the video) and the
// exported MP4. Needs the API running on :8001 (see docs/HANDOFF.md).
//
//   node scripts/tutorials/capture-studio.mjs <recipe.json> <out-dir>
//
// A recipe is { "image": path, "name": "file name shown in the app", "style": "ink"|"pencil",
//               "pen": bool, "color": bool, "duration": seconds, "ratio": "9:16", "resolution": "1080p",
//               "steps": bool (use the app's drawing-steps mode) }
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const [recipePath, outDir] = process.argv.slice(2);
const recipe = JSON.parse(fs.readFileSync(recipePath, 'utf8'));
const APP = process.env.STROKEBERRY_URL || 'http://127.0.0.1:8001';
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const W = 390, H = 844, DPR = 3;
fs.mkdirSync(outDir, {recursive: true});

const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await puppeteer.launch({executablePath: CHROME, headless: 'new', args: ['--hide-scrollbars']});
const page = await browser.newPage();
await page.setViewport({width: W, height: H, deviceScaleFactor: DPR, isMobile: true, hasTouch: true});
await page.goto(`${APP}/studio/`, {waitUntil: 'networkidle0'});
await sleep(2500);

const shots = [];
async function rectOf(selector, text) {
  return page.evaluate((selector, text) => {
    const els = [...document.querySelectorAll(selector)];
    const el = text ? els.find(e => e.textContent.trim().includes(text)) : els[0];
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: r.x, y: r.y, w: r.width, h: r.height};
  }, selector, text);
}
async function scrollTo(selector, text, offset = 120) {
  await page.evaluate((selector, text, offset) => {
    const els = [...document.querySelectorAll(selector)];
    const el = text ? els.find(e => e.textContent.trim().includes(text)) : els[0];
    window.scrollTo(0, Math.max(0, el.getBoundingClientRect().top + window.scrollY - offset));
  }, selector, text, offset);
  await sleep(400);
}
async function click(selector, text) {
  await page.evaluate((selector, text) => {
    const els = [...document.querySelectorAll(selector)];
    const el = text ? els.find(e => e.textContent.trim().includes(text)) : els[0];
    el.click();
  }, selector, text);
  await sleep(700);
}
async function shot(id, targets = {}) {
  const file = `${id}.png`;
  await page.screenshot({path: path.join(outDir, file)});
  const rects = {};
  for (const [name, [selector, text]] of Object.entries(targets)) rects[name] = await rectOf(selector, text);
  shots.push({id, file, rects});
  console.log('  ', file);
}
async function waitIdle() {
  await page.waitForFunction(() => !document.querySelector('.canvas-loading .spin'), {timeout: 120000});
  await sleep(1500);
}

// 1. Start: the studio, with the Replace button that opens the file picker.
await scrollTo('.preview-stage', null, 70);
await shot('01-start', {replace: ['.source-actions button', 'Replace'], preview: ['.preview-stage'], steps: ['.steps-entry']});

// 2. Upload the image.
const input = await page.$('input[type=file]');
const staged = path.join(outDir, recipe.name);
fs.copyFileSync(recipe.image, staged);
await input.uploadFile(staged);
await sleep(600);
await shot('02-uploading', {preview: ['.preview-stage']});
await waitIdle();
await page.evaluate(() => { const b = document.querySelector('.playback button'); if (b && b.getAttribute('aria-label') === 'Pause preview') b.click(); });
await shot('03-uploaded', {preview: ['.preview-stage'], source: ['.source-row'], steps: ['.steps-entry']});

// 3. Drawing style.
await scrollTo('.settings-panel', null, 20);
await shot('04-settings', {tab: ['.settings-tabs button', 'Drawing style'], pencil: ['.style-card', 'Pencil'], ink: ['.style-card', 'Ink']});
if (recipe.style === 'ink') await click('.style-card', 'Ink');
else await click('.style-card', 'Pencil');
await shot('05-style', {pencil: ['.style-card', 'Pencil'], ink: ['.style-card', 'Ink']});
for (const [label, want] of [['Show drawing pencil', recipe.pen], ['Bring in the color', recipe.color]]) {
  const on = await page.evaluate(label => [...document.querySelectorAll('.toggle-row')].find(t => t.textContent.includes(label))?.getAttribute('aria-checked'), label);
  if (on !== null && on !== undefined && (on === 'true') !== want) await click('.toggle-row', label);
}
await shot('06-toggles', {pen: ['.toggle-row', 'Show drawing pencil'], color: ['.toggle-row', 'Bring in the color'], duration: ['.duration-slider']});

// 4. Video settings.
await click('.settings-tabs button', 'Video settings');
await shot('07-video-tab', {tab: ['.settings-tabs button', 'Video settings'], ratio: ['.ratio-options button', recipe.ratio]});
await click('.ratio-options button', recipe.ratio);
await page.select('#resolution', recipe.resolution);
await sleep(500);
await shot('08-video-set', {ratio: ['.ratio-options button', recipe.ratio], quality: ['#resolution'], summary: ['.export-summary']});

// 5. Preview.
await scrollTo('.preview-stage', null, 70);
await page.evaluate(() => { const b = document.querySelector('.playback button'); if (b && b.getAttribute('aria-label') === 'Play preview') b.click(); });
for (let i = 0; i < 4; i++) {
  await sleep(recipe.duration * 1000 / 5);
  await shot(`09-preview-${i + 1}`, {preview: ['.preview-stage'], play: ['.playback button']});
}
await sleep(recipe.duration * 1000 / 4);

// 6. Export.
await scrollTo('.export-button', null, 420);
await shot('10-export', {export: ['.export-button']});
await click('.export-button');
await sleep(1200);
await shot('11-exporting', {dialog: ['[role=dialog]']});
await page.waitForFunction(() => [...document.querySelectorAll('[role=dialog] a, [role=dialog] button')].some(e => e.textContent.includes('Download MP4')), {timeout: 600000});
await sleep(800);
await shot('12-ready', {dialog: ['[role=dialog]'], download: ['[role=dialog] a, [role=dialog] button', 'Download MP4']});
const href = await page.evaluate(() => [...document.querySelectorAll('[role=dialog] a')].find(a => a.textContent.includes('Download MP4'))?.href);
if (href) {
  const buf = Buffer.from(await (await fetch(href)).arrayBuffer());
  fs.writeFileSync(path.join(outDir, 'result.mp4'), buf);
  console.log('   result.mp4', buf.length, 'bytes');
} else console.warn('  no download link found');

fs.writeFileSync(path.join(outDir, 'shots.json'), JSON.stringify({viewport: {w: W, h: H, dpr: DPR}, recipe, shots}, null, 2));
fs.unlinkSync(staged);
await browser.close();
