import { Camera } from "lucide-react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import data from "../data.json";
import { Backdrop, Brackets, clamp, display, easeInOut, Exit, Kicker, ScanSweep, useSpring, Words } from "../kit";
import { alpha, c, mono } from "../theme";

const tile = 560;
const tiles = [
  { src: "img/m7-synth.jpg", label: "SYNTHETIC", sub: "Blender render", box: data.synth, x: 960 - 40 - tile, color: c.primary },
  { src: "img/m7-real.jpg", label: "REAL", sub: "VEO scan", box: data.real, x: 960 + 40, color: c.veo },
];
const top = 380;
const cam = { x: 960, y: 200 };

function Pro3({ s }: { s: number }) {
  const frame = useCurrentFrame();
  const ping = (frame % 40) / 40;
  return (
    <div style={{ position: "absolute", left: cam.x - 75, top: cam.y - 125, width: 150, height: 150, transform: `scale(${s})` }}>
      <div style={{ position: "absolute", inset: -ping * 40, borderRadius: "50%", border: `3px solid ${c.veo}`, opacity: 1 - ping }} />
      <div style={{ position: "absolute", inset: 0, borderRadius: "50%", display: "grid", placeItems: "center", background: `radial-gradient(circle, ${c.card}, ${c.deep})`, border: `3px solid ${c.veo}`, boxShadow: `0 0 60px ${alpha(c.veo, 0.6)}` }}>
        <Camera size={76} color={c.foreground} strokeWidth={1.8} />
      </div>
    </div>
  );
}

export function M07OneCamera() {
  const frame = useCurrentFrame();
  const camS = useSpring(4, { damping: 12 });
  const beam = interpolate(frame, [18, 40], [0, 1], { ...clamp, easing: easeInOut });
  const lock = useSpring(78, { damping: 11, stiffness: 160 });

  return (
    <Exit>
      <Backdrop grid={false}>
        <AbsoluteFill style={{ alignItems: "flex-start", padding: "70px 110px" }}>
          <Kicker color={c.veo} delay={2}>Same camera, same view</Kicker>
        </AbsoluteFill>
        <svg width={1920} height={1080} style={{ position: "absolute" }}>
          {tiles.map((t) =>
            [t.x, t.x + tile].map((x, j) => (
              <line key={`${t.label}${j}`} x1={cam.x} y1={cam.y - 50} x2={cam.x + (x - cam.x) * beam} y2={cam.y - 50 + (top - cam.y + 50) * beam} stroke={t.color} strokeWidth={2.5} opacity={0.7} strokeDasharray="10 8" strokeDashoffset={-frame * 2} />
            )),
          )}
          {tiles.map((t) => (
            <polygon key={t.label} points={`${cam.x},${cam.y - 50} ${t.x},${top} ${t.x + tile},${top}`} fill={alpha(t.color, 0.08 * beam)} />
          ))}
        </svg>
        <Pro3 s={camS} />
        <div style={{ position: "absolute", left: cam.x + 100, top: cam.y - 90, display: "flex", flexDirection: "column", gap: 10, opacity: camS, transform: `translateX(${(1 - camS) * 40}px)` }}>
          <Img src={staticFile("logos/matterport-logo.svg")} style={{ height: 44, width: "auto", alignSelf: "flex-start" }} />
          <span style={{ fontFamily: mono, fontSize: 26, color: c.foreground, fontWeight: 600 }}>Pro3 · same lens, same FOV</span>
        </div>
        {tiles.map((t, i) => {
          const s = useSpring(30 + i * 8, { damping: 14, stiffness: 90 });
          const b = t.box;
          return (
            <div key={t.label} style={{ position: "absolute", left: t.x, top, width: tile, perspective: 1200 }}>
              <div style={{ position: "relative", width: tile, height: tile, borderRadius: 22, overflow: "hidden", border: `2px solid ${t.color}`, boxShadow: `0 0 60px -10px ${t.color}`, transform: `rotateY(${(1 - s) * (i ? -90 : 90)}deg)`, opacity: s }}>
                <Img src={staticFile(t.src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                <ScanSweep at={56} duration={26} color={c.ok} vertical />
                <div style={{ position: "absolute", left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%`, transform: `scale(${1.6 - 0.6 * lock})` }}>
                  <Brackets w={b.w * tile} h={b.h * tile} progress={lock} color={c.ok} thickness={5} />
                </div>
                <div style={{ position: "absolute", left: 18, top: 18, fontFamily: mono, fontSize: 22, fontWeight: 700, letterSpacing: "0.2em", padding: "8px 14px", borderRadius: 10, background: alpha(c.void, 0.8), color: t.color, border: `1.5px solid ${t.color}` }}>{t.label}</div>
                <div style={{ position: "absolute", right: 18, bottom: 18, fontFamily: mono, fontSize: 20, padding: "6px 12px", borderRadius: 8, background: alpha(c.void, 0.8), color: c.muted }}>{t.sub}</div>
              </div>
            </div>
          );
        })}
        <AbsoluteFill style={{ top: 980, height: 80, alignItems: "center" }}>
          <Words text="One camera: Matterport Pro3" delay={110} style={{ ...display, fontSize: 56, fontWeight: 650 }} wordStyle={(i) => (i >= 2 ? { color: c.veo } : {})} />
        </AbsoluteFill>
      </Backdrop>
    </Exit>
  );
}
