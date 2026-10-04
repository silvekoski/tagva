import { renameSync } from "node:fs";
import { record } from "./record.mjs";

const TAGS = new URL("../data/tags/VEO-DEMO.json", import.meta.url).pathname;

const relay = (page, cabinet) =>
  page.locator("#tag-list > li").filter({ hasText: cabinet }).locator("button[data-key^=dev]").first();

const HIDE_UI = `
  .stage { position: fixed !important; inset: 0 !important; z-index: 40; }
  #overlay, .stage > p[role=status], [data-sonner-toaster], #rec-cursor { display: none !important; }
`;

const sine = (k) => k - Math.sin(2 * Math.PI * k) / (2 * Math.PI);

const STOPWATCH = (label) => `
  (() => {
    const el = document.createElement("div");
    el.id = "rec-clock";
    el.style.cssText = "position:fixed;top:58px;right:16px;z-index:60;padding:8px 14px;border-radius:10px;background:rgba(10,14,24,.82);border:1px solid rgba(255,255,255,.14);color:#fff;font:600 28px/1.1 'Geist Mono Variable',ui-monospace,monospace;letter-spacing:.02em;box-shadow:0 4px 18px rgba(0,0,0,.35)";
    el.innerHTML = '<div style="font:500 11px/1.4 Geist Variable,system-ui;letter-spacing:.08em;text-transform:uppercase;opacity:.7">${label}</div><span>0:00.0</span>';
    document.body.appendChild(el);
    const out = el.querySelector("span");
    let t0 = 0, stopped = false;
    const fmt = (ms) => { const s = ms / 1000; return Math.floor(s / 60) + ":" + (s % 60).toFixed(1).padStart(4, "0"); };
    const tick = () => { if (!stopped && t0) out.textContent = fmt(performance.now() - t0); requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    window.__clock = { start: () => (t0 = performance.now()), stop: () => { stopped = true; out.textContent = fmt(performance.now() - t0); } };
  })();`;

async function faceRelays(page, t) {
  await relay(page, "H03 METERING").click();
  await t.wait(1500);
  await page.keyboard.press("Escape");
  await t.wait(500);
}

export const clips = {
  async t1() {
    await record("t1-panorama-pan", "?sweep=sweep-12", async (page, t) => {
      await t.wait(4000);
      await t.move(1500, 540, 10);
      await t.drag(-640, 0, 16000, { curve: (k) => k - Math.sin(2 * Math.PI * k) / (2 * Math.PI) });
      await t.wait(500);
    }, {
      cursor: false,
      async before(page, t) {
        await relay(page, "H03 METERING").click();
        await t.wait(1500);
        await page.keyboard.press("Escape");
        await t.css(HIDE_UI);
        await page.mouse.move(1500, 540);
        await page.mouse.down();
        await page.mouse.move(1820, 540, { steps: 20 });
        await page.mouse.up();
        await t.wait(1500);
      },
    });
  },

  async t2() {
    renameSync(TAGS, `${TAGS}.hidden`);
    try {
      await record("t2-run-detection", "?sweep=sweep-12", async (page, t) => {
        await t.wait(1500);
        await t.click(page.getByRole("button", { name: "Scan all positions" }), 1200);
        await page.evaluate(() => window.__clock.start());
        t.mark("click");
        await page.getByText("The run is complete").first().waitFor({ timeout: 15 * 60_000 });
        await page.evaluate(() => window.__clock.stop());
        t.mark("done");
        await t.wait(3000);
        await t.move(130, 760, 1500);
        await t.wait(4000);
        await t.move(1100, 560, 1500);
        await t.wait(5000);
      }, {
        async before(page, t) {
          await page.mouse.move(1500, 540);
          await page.mouse.down();
          await page.mouse.move(800, 540, { steps: 30 });
          await page.mouse.up();
          await page.evaluate(STOPWATCH("Run time"));
          await page.mouse.move(960, 600);
          await t.wait(1500);
        },
      });
    } finally {
      try {
        renameSync(`${TAGS}.hidden`, `${TAGS}.before-run`);
      } catch {}
    }
  },

  async t4() {
    await record("t4-synthetic-gallery", "?sweep=sweep-12", async (page, t) => {
      await t.wait(800);
      await t.click(page.getByRole("button", { name: "Dataset" }));
      await t.wait(3500);
      await t.move(960, 700, 900);
      for (let i = 0; i < 40; i++) {
        await page.mouse.wheel(0, 18);
        await t.wait(40);
      }
      await t.wait(1200);
      await t.click(page.getByRole("radio", { name: "Dark" }));
      await t.wait(2500);
      await t.click(page.locator("[data-thumb='1']"));
      await t.wait(3500);
      await page.keyboard.press("Escape");
      await t.wait(800);
      await t.click(page.getByRole("tab", { name: /heavy-occlusion/ }));
      await t.wait(2500);
      await t.click(page.locator("[data-thumb='0']"));
      await t.wait(3500);
      await page.keyboard.press("Escape");
      await t.wait(1000);
    });
  },

  async t5() {
    await record("t5-dollhouse-orbit", "?sweep=sweep-12", async (page, t) => {
      await t.wait(800);
      await t.click(page.getByRole("radio", { name: "Dollhouse" }));
      await page.locator(".sweep-dot").first().waitFor();
      await t.wait(4000);
      await t.move(1100, 560, 900);
      await t.drag(-520, 40, 14000, { curve: sine });
      await t.wait(1000);
    });
  },

  async t6() {
    await record("t6-show-boxes", "?sweep=sweep-12", async (page, t) => {
      await t.wait(1000);
      await t.click(page.getByRole("button", { name: "Show boxes" }));
      await t.wait(4000);
      await t.hover(page.locator("#overlay .pin.cabinet", { hasText: "H03 METERING" }), 1500);
      await t.wait(3000);
      await t.hover(page.locator("#overlay .pin.cabinet", { hasText: "H02" }), 1200);
      await t.wait(2500);
    }, { before: faceRelays });
  },

  async t7() {
    await record("t7-device-manual", "?sweep=sweep-12", async (page, t) => {
      await t.wait(1000);
      await t.click(page.locator("#overlay .pin.device:not([hidden])").first(), 1200);
      await t.wait(3000);
      await t.click(page.getByRole("tab", { name: /Documents/ }));
      await t.wait(2500);
      await t.click(page.getByRole("button", { name: /Read the LEDs/ }));
      await t.wait(6000);
    }, { before: faceRelays });
  },

  async t8() {
    await record("t8-review-editor", "?sweep=sweep-12", async (page, t) => {
      await t.wait(1000);
      await t.hover(page.getByRole("slider", { name: "Review threshold" }), 1200);
      await t.drag(-90, 0, 2500, { curve: sine });
      await t.wait(1200);
      await t.drag(130, 0, 2500, { curve: sine });
      await t.wait(1500);
      await t.drag(-40, 0, 1200, { curve: sine });
      await t.wait(1200);
      await t.click(relay(page, "H05 SOLAR2"), 1200);
      await t.wait(2500);
      await t.click(page.getByRole("button", { name: "Edit device" }));
      await t.wait(1200);
      await page.getByLabel("Name").fill("");
      await t.type("H05 SOLAR2 REX615", 80);
      await t.wait(1000);
      await t.click(page.getByRole("button", { name: "Save" }));
      await t.wait(4000);
    }, { before: faceRelays });
  },

  async t9() {
    await record("t9-browser-detection", "?sweep=sweep-12", async (page, t) => {
      await t.wait(1000);
      await t.click(page.getByRole("button", { name: "Check this view" }), 1200);
      await page.evaluate(() => window.__clock.start());
      await page.getByRole("button", { name: "Check this view" }).and(page.locator(":enabled")).waitFor({ timeout: 120_000 });
      await page.evaluate(() => window.__clock.stop());
      await t.wait(2500);
      await t.click(page.getByRole("button", { name: "Show boxes" }));
      await t.wait(5000);
    }, {
      async before(page, t) {
        await faceRelays(page, t);
        await page.evaluate(STOPWATCH("Browser, WebGPU"));
      },
    });
  },
};

for (const name of process.argv.slice(2)) await clips[name]();
