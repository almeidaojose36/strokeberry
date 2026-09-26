#!/usr/bin/env node
// Drives the real Strokeberry studio at phone size through a scripted flow and captures each step as a
// 3x screenshot, with the rectangles of the controls to highlight. A generalised capture-studio.mjs:
// the recipe lists the actions, so every tutorial can script its own path through the app.
//
//   node scripts/tutorials/capture-flow.mjs <flow.json> <out-dir>
//
// flow.json: { "image": path, "name": file name shown in the app, "actions": [ ... ] }
// Actions (one key each, run in order):
//   {"scroll": [selector, text?, offsetPx]}      scroll the page so the element sits offsetPx from the top
//   {"scrollIn": [container, selector?, text?, offsetPx]}  scroll inside a scrolling container (e.g. a dialog)
//   {"click": [selector, text?]}                 click an element (text = substring match)
//   {"upload": true}                             choose the recipe's image in the file input and wait for it to load
//   {"select": [selector, value]}                set a <select>
//   {"range": [selector, value]}                 set a range input (React-safe)
//   {"play": true} / {"pause": true}             start or stop the preview
//   {"wait": ms}                                 wait
//   {"waitFor": [selector, text?, timeoutMs]}    wait until an element (with text) exists
//   {"shot": id, "targets": {name: [selector, text?]}}   screenshot + target rectangles
//   {"download": true}                           save the finished export as result.mp4
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const [flowPath, outDir] = process.argv.slice(2);
const flow = JSON.parse(fs.readFileSync(flowPath, 'utf8'));
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

// Runs in the page: find the first element matching selector (and containing text, if given).
const FIND = `(selector, text) => { const els = [...document.querySelectorAll(selector)];
  return text ? els.find(e => (e.getAttribute('aria-label') || '').includes(text) || e.textContent.trim().includes(text)) : els[0]; }`;
const inPage = (body, ...args) => page.evaluate(new Function('args', `const find = ${FIND}; return (${body})(...args);`), args);

const shots = [];
const staged = path.join(outDir, flow.name);
fs.copyFileSync(flow.image, staged);
const waitIdle = async () => {
  await page.waitForFunction(() => !document.querySelector('.canvas-loading .spin'), {timeout: 180000});
  await sleep(1500);
};

for (const a of flow.actions) {
  if (a.scroll) {
    const [sel, text, off = 120] = a.scroll;
    await inPage(`(sel, text, off) => { const el = find(sel, text); window.scrollTo(0, Math.max(0, el.getBoundingClientRect().top + window.scrollY - off)); }`, sel, text, off);
    await sleep(500);
  } else if (a.scrollIn) {
    const [box, sel, text, off = 40] = a.scrollIn;
    await inPage(`(box, sel, text, off) => { const c = document.querySelector(box);
      if (!sel) { c.scrollTop = c.scrollHeight; return; }
      const el = find(sel, text); c.scrollTop += el.getBoundingClientRect().top - c.getBoundingClientRect().top - off; }`, box, sel, text, off);
    await sleep(500);
  } else if (a.click) {
    await inPage(`(sel, text) => find(sel, text).click()`, a.click[0], a.click[1]);
    await sleep(800);
  } else if (a.upload) {
    await (await page.$('input[type=file]')).uploadFile(staged);
    // Wait until the new image is the project (the sample stays on screen until the upload is processed).
    const stem = path.parse(flow.name).name;
    await page.waitForFunction(stem => document.querySelector('.source-row')?.textContent.includes(stem), {timeout: 180000}, stem);
    await waitIdle();
    await inPage(`() => { const b = document.querySelector('.playback button'); if (b && b.getAttribute('aria-label') === 'Pause preview') b.click(); }`);
  } else if (a.select) {
    await page.select(a.select[0], a.select[1]);
    await sleep(500);
  } else if (a.range) {
    await inPage(`(sel, v) => { const el = document.querySelector(sel);
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, String(v));
      el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }`, a.range[0], a.range[1]);
    await sleep(500);
  } else if (a.play || a.pause) {
    const want = a.play ? 'Play preview' : 'Pause preview';
    await inPage(`(want) => { const b = document.querySelector('.playback button'); if (b && b.getAttribute('aria-label') === want) b.click(); }`, want);
    await sleep(300);
  } else if (a.wait) {
    await sleep(a.wait);
  } else if (a.waitFor) {
    const [sel, text, timeout = 180000] = a.waitFor;
    await page.waitForFunction(new Function('sel', 'text', `const find = ${FIND}; return !!find(sel, text);`), {timeout}, sel, text);
    await sleep(800);
  } else if (a.shot) {
    await page.screenshot({path: path.join(outDir, `${a.shot}.png`)});
    const rects = {};
    for (const [name, [sel, text]] of Object.entries(a.targets || {})) {
      rects[name] = await inPage(`(sel, text) => { const el = find(sel, text); if (!el) return null;
        const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; }`, sel, text);
      if (!rects[name]) console.warn(`   ! ${a.shot}: target "${name}" not found`);
    }
    shots.push({id: a.shot, file: `${a.shot}.png`, rects});
    console.log('  ', `${a.shot}.png`);
  } else if (a.download) {
    const href = await inPage(`() => [...document.querySelectorAll('[role=dialog] a')].find(x => x.textContent.includes('Download MP4'))?.href`);
    if (!href) throw new Error('no Download MP4 link');
    const buf = Buffer.from(await (await fetch(href)).arrayBuffer());
    fs.writeFileSync(path.join(outDir, 'result.mp4'), buf);
    console.log('   result.mp4', buf.length, 'bytes');
  }
}

fs.writeFileSync(path.join(outDir, 'shots.json'), JSON.stringify({viewport: {w: W, h: H, dpr: DPR}, flow: flow.name, shots}, null, 2));
fs.unlinkSync(staged);
await browser.close();
