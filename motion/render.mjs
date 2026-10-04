import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const args = process.argv.slice(2);
const stills = args.includes("--stills");
const only = args.filter((a) => !a.startsWith("--"));
const overlays = new Set(["m01-title", "m04-results", "m12-dark-recall"]);
const out = path.resolve("out");
await mkdir(out, { recursive: true });

const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
const { getCompositions } = await import("@remotion/renderer");
const ids = (await getCompositions(serveUrl)).map((c) => c.id).filter((id) => !only.length || only.includes(id));

for (const id of ids) {
  const composition = await selectComposition({ serveUrl, id });
  if (composition.durationInFrames === 1) {
    await renderStill({ serveUrl, composition, output: path.join(out, `${id}.png`), imageFormat: "png" });
    console.log("png", id);
    continue;
  }
  if (stills) {
    for (const t of [0.35, 0.8]) {
      const frame = Math.floor(composition.durationInFrames * t);
      await renderStill({ serveUrl, composition, frame, output: path.join(out, "stills", `${id}-${frame}.jpg`), imageFormat: "jpeg", jpegQuality: 80 });
    }
    console.log("still", id);
    continue;
  }
  await renderMedia({ serveUrl, composition, codec: "h264", crf: 16, pixelFormat: "yuv420p", outputLocation: path.join(out, `${id}.mp4`) });
  console.log("mp4", id);
  if (overlays.has(id)) {
    const alpha = await selectComposition({ serveUrl, id, inputProps: { overlay: true } });
    await renderMedia({ serveUrl, composition: alpha, inputProps: { overlay: true }, codec: "prores", proResProfile: "4444", imageFormat: "png", pixelFormat: "yuva444p10le", outputLocation: path.join(out, `${id}-alpha.mov`) });
    console.log("alpha", id);
  }
}
