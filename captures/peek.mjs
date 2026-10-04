import { chromium } from "/Users/veikka/yard-service/node_modules/playwright/index.mjs";
const browser = await chromium.launch({ channel: "chrome", args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-webgpu"] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(process.argv[2]);
await page.waitForTimeout(5000);
for (const step of (process.argv[4] ?? "").split("|").filter(Boolean)) {
  const [k, ...a] = step.split(":"); const r = a.join(":");
  if (k === "click") await page.getByRole(a[0], { name: a.slice(1).join(":"), exact: false }).first().click();
  else if (k === "text") await page.getByText(r).first().click();
  else if (k === "wait") await page.waitForTimeout(+r);
  else if (k === "key") await page.keyboard.press(r);
  else if (k === "eval") console.log(await page.evaluate(r));
}
await page.screenshot({ path: process.argv[3] });
await browser.close();
