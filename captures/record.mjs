import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "/Users/veikka/yard-service/node_modules/playwright/index.mjs";

const BASE = process.env.TAGVA_URL ?? "http://127.0.0.1:5173/";
const OUT = new URL("./clips/", import.meta.url).pathname;
const W = 1920;
const H = 1080;

const CURSOR = `
(() => {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28"><path d="M4 2 L4 22 L9.5 17 L13 25 L16.5 23.5 L13 15.8 L20.5 15.8 Z" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  const add = () => {
    const c = document.createElement("div");
    c.id = "rec-cursor";
    c.innerHTML = svg;
    c.style.cssText = "position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);filter:drop-shadow(0 1px 2px rgba(0,0,0,.45))";
    document.documentElement.appendChild(c);
    const ring = document.createElement("div");
    ring.style.cssText = "position:fixed;left:0;top:0;width:36px;height:36px;margin:-18px 0 0 -18px;border-radius:50%;border:3px solid rgba(255,255,255,.9);z-index:2147483646;pointer-events:none;opacity:0";
    document.documentElement.appendChild(ring);
    addEventListener("pointermove", (e) => (c.style.transform = "translate(" + (e.clientX - 4) + "px," + (e.clientY - 2) + "px)"), true);
    addEventListener("pointerdown", (e) => {
      ring.style.left = e.clientX + "px";
      ring.style.top = e.clientY + "px";
      ring.animate([{ opacity: 1, transform: "scale(.4)" }, { opacity: 0, transform: "scale(1.3)" }], { duration: 450, easing: "ease-out" });
    }, true);
  };
  if (document.documentElement) add(); else addEventListener("DOMContentLoaded", add);
})();`;

export async function record(name, url, body, { cursor = true, settle = 6000, before } = {}) {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    channel: "chrome",
    args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-webgpu", "--enable-features=Vulkan,WebGPU"],
  });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  if (cursor) await page.addInitScript(CURSOR);
  await page.goto(BASE + url);
  await page.waitForTimeout(settle);
  const frames = [];
  const marks = {};
  const t = createTools(page, marks, frames);
  await before?.(page, t);
  await page.screencast.start({
    size: { width: W, height: H },
    quality: 95,
    onFrame: (f) => frames.push({ data: f.data, ts: f.timestamp }),
  });
  try {
    await body(page, t);
    await page.waitForTimeout(300);
  } finally {
    await page.screencast.stop();
    await browser.close();
  }
  await encode(name, frames);
  if (Object.keys(marks).length) writeFileSync(`${OUT}${name}.marks.json`, JSON.stringify(marks, null, 2) + "\n");
  return marks;
}

async function encode(name, frames) {
  if (frames.length < 2) throw new Error(`${name}: only ${frames.length} frames`);
  const ff = spawn("ffmpeg", [
    "-y", "-loglevel", "error", "-framerate", "60", "-f", "image2pipe", "-c:v", "mjpeg", "-i", "-",
    "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-movflags", "+faststart", `${OUT}${name}.mp4`,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  const done = new Promise((res, rej) => ff.on("close", (code) => (code ? rej(new Error(`ffmpeg exit ${code}`)) : res())));
  const t0 = frames[0].ts;
  const end = frames.at(-1).ts + 300;
  let i = 0;
  for (let t = t0; t < end; t += 1000 / 60) {
    while (i + 1 < frames.length && frames[i + 1].ts <= t) i++;
    if (!ff.stdin.write(frames[i].data)) await new Promise((r) => ff.stdin.once("drain", r));
  }
  ff.stdin.end();
  await done;
  console.log(`${name}.mp4: ${((end - t0) / 1000).toFixed(1)} s, ${frames.length} source frames`);
}

const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2);

async function glide(page, from, to, ms, curve) {
  const t0 = performance.now();
  const sent = [];
  for (;;) {
    const k = Math.min(1, (performance.now() - t0) / ms);
    const c = curve(k);
    sent.push(page.mouse.move(from.x + (to.x - from.x) * c, from.y + (to.y - from.y) * c));
    if (k === 1) break;
    await new Promise((r) => setTimeout(r, 16));
  }
  await Promise.all(sent);
}

function createTools(page, marks, frames) {
  let pos = { x: W / 2, y: H / 2 };
  const tools = {
    wait: (ms) => page.waitForTimeout(ms),
    mark: (key) => (marks[key] = frames.length ? (frames.at(-1).ts - frames[0].ts) / 1000 : 0),
    async move(x, y, ms = 700) {
      await glide(page, pos, { x, y }, ms, ease);
      pos = { x, y };
    },
    async center(locator) {
      const b = await locator.boundingBox();
      if (!b) throw new Error(`no box for ${locator}`);
      return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
    },
    async hover(locator, ms = 700) {
      await locator.scrollIntoViewIfNeeded();
      const c = await tools.center(locator);
      await tools.move(c.x, c.y, ms);
    },
    async click(locator, ms = 700) {
      await tools.hover(locator, ms);
      await page.waitForTimeout(150);
      await page.mouse.down();
      await page.waitForTimeout(90);
      await page.mouse.up();
    },
    async drag(dx, dy, ms, { button = "left", curve = (k) => k } = {}) {
      const to = { x: pos.x + dx, y: pos.y + dy };
      await page.mouse.down({ button });
      await glide(page, pos, to, ms, curve);
      await page.mouse.up({ button });
      pos = to;
    },
    async type(text, delay = 90) {
      await page.keyboard.type(text, { delay });
    },
    css: (text) => page.addStyleTag({ content: text }),
  };
  return tools;
}
