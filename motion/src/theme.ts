import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import { continueRender, delayRender } from "remotion";

export const sans = '"Geist Variable", ui-sans-serif, system-ui, sans-serif';
export const mono = '"Geist Mono Variable", ui-monospace, monospace';

const fonts = delayRender("Load the Geist fonts");
Promise.all(["Geist Variable", "Geist Mono Variable"].map((f) => document.fonts.load(`400 1em "${f}"`))).then(() => continueRender(fonts));

export const c = {
  background: "oklch(0.2077 0.0398 265.7549)",
  deep: "oklch(0.13 0.035 266)",
  void: "oklch(0.09 0.025 266)",
  foreground: "oklch(0.9288 0.0126 255.5078)",
  card: "oklch(0.2795 0.0368 260.0310)",
  secondary: "oklch(0.3351 0.0331 260.9120)",
  muted: "oklch(0.7137 0.0192 261.3246)",
  border: "oklch(0.4461 0.0263 256.8018)",
  primary: "oklch(0.6801 0.1583 276.9349)",
  chart2: "oklch(0.5854 0.2041 277.1173)",
  chart3: "oklch(0.5106 0.2301 276.9656)",
  chart4: "oklch(0.4568 0.2146 277.0229)",
  destructive: "oklch(0.6368 0.2078 25.3313)",
  review: "oklch(0.8131 0.165 75.0445)",
  ok: "oklch(0.793 0.1803 153.9981)",
  browser: "oklch(0.8203 0.1377 217.8723)",
  veo: "oklch(0.7080 0.1489 234.3628)",
  tagva: "#08329B",
} as const;

export const alpha = (color: string, a: number) => color.replace(")", ` / ${a})`);

export const brand = `linear-gradient(100deg, ${c.foreground} 0%, ${c.primary} 55%, ${c.veo} 100%)`;
