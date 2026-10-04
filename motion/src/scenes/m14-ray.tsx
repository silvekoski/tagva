import { Camera } from "lucide-react";
import { AbsoluteFill, interpolate, random, useCurrentFrame } from "remotion";
import { Backdrop, clamp, display, easeInOut, easeOut, Exit, Kicker, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const target = { x: 1480, y: 470 };
const cams = [
  { x: 250, y: 400, at: 34, color: c.primary, label: "sweep-02" },
  { x: 520, y: 760, at: 104, color: c.veo, label: "sweep-03" },
];
const cloud = (() => {
  const pts: { x: number; y: number; k: number }[] = [];
  for (let i = 0; i < 900; i++) {
    const r = random(`p${i}`);
    if (r < 0.55) pts.push({ x: 1480 + random(`a${i}`) ** 3 * 220, y: 170 + random(`b${i}`) * 740, k: i });
    else if (r < 0.75) pts.push({ x: 1480 + random(`a${i}`) * 220, y: 170 + random(`b${i}`) * 10, k: i });
    else pts.push({ x: 120 + random(`a${i}`) * 1640, y: 920 + random(`b${i}`) * 26, k: i });
  }
  return pts;
})();

function Ray({ cam }: { cam: (typeof cams)[number] }) {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [cam.at, cam.at + 32], [0, 1], { ...clamp, easing: easeInOut });
  const hx = cam.x + (target.x - cam.x) * p;
  const hy = cam.y + (target.y - cam.y) * p;
  const bx = cam.x + (target.x - cam.x) * 0.3;
  const by = cam.y + (target.y - cam.y) * 0.3;
  const box = interpolate(frame, [cam.at + 6, cam.at + 14], [0, 1], clamp);
  return (
    <g>
      <line x1={cam.x} y1={cam.y} x2={hx} y2={hy} stroke={cam.color} strokeWidth={4} style={{ filter: `drop-shadow(0 0 10px ${cam.color})` }} />
      {p > 0 && p < 1 && <circle cx={hx} cy={hy} r={10} fill={c.foreground} style={{ filter: `drop-shadow(0 0 14px ${cam.color})` }} />}
      <rect x={bx - 34} y={by - 26} width={68} height={52} rx={4} fill={alpha(c.ok, 0.12 * box)} stroke={c.ok} strokeWidth={3} opacity={box} transform={`rotate(${Math.atan2(target.y - cam.y, target.x - cam.x) * (180 / Math.PI)} ${bx} ${by})`} />
    </g>
  );
}

export function M14Ray() {
  const frame = useCurrentFrame();
  const hitA = interpolate(frame, [66, 96], [0, 1], { ...clamp, easing: easeOut });
  const hitB = interpolate(frame, [136, 170], [0, 1], { ...clamp, easing: easeOut });
  const merged = useSpring(140, { damping: 10, stiffness: 160 });
  const callout = useSpring(160, { damping: 15 });

  return (
    <Exit>
      <Backdrop grid={false}>
        <AbsoluteFill style={{ padding: "64px 110px" }}>
          <Kicker color={c.veo}>Box to 3D anchor · side view</Kicker>
        </AbsoluteFill>
        <svg width={1920} height={1080} style={{ position: "absolute" }}>
          {cloud.map((p) => {
            const s = interpolate(frame, [random(`t${p.k}`) * 24, 24 + random(`t${p.k}`) * 24], [0, 1], { ...clamp, easing: easeOut });
            const sx = (random(`sx${p.k}`) - 0.5) * 900;
            const sy = (random(`sy${p.k}`) - 0.5) * 900;
            const tw = 0.4 + 0.6 * Math.abs(Math.sin(frame / 20 + p.k));
            return <circle key={p.k} cx={p.x + sx * (1 - s)} cy={p.y + sy * (1 - s)} r={1.8} fill={p.x > 1470 && p.y < 915 ? c.browser : c.muted} opacity={s * tw * 0.8} />;
          })}
          <line x1={1478} y1={170} x2={1478} y2={910} stroke={alpha(c.browser, 0.5)} strokeWidth={2} strokeDasharray="6 8" opacity={interpolate(frame, [20, 40], [0, 1], clamp)} />
          {cams.map((cam) => (
            <Ray key={cam.label} cam={cam} />
          ))}
          <circle cx={target.x} cy={target.y} r={20 + hitA * 120} fill="none" stroke={c.primary} strokeWidth={4 * (1 - hitA)} opacity={frame > 66 ? 1 - hitA : 0} />
          <circle cx={target.x} cy={target.y} r={20 + hitB * 160} fill="none" stroke={c.veo} strokeWidth={5 * (1 - hitB)} opacity={frame > 136 ? 1 - hitB : 0} />
          {frame > 66 && <circle cx={target.x} cy={target.y} r={13 + merged * 5} fill={c.ok} style={{ filter: `drop-shadow(0 0 ${12 + merged * 18}px ${c.ok})` }} />}
        </svg>
        {cams.map((cam) => {
          const s = useSpring(cam.at - 20, { damping: 12, stiffness: 150 });
          return (
            <div key={cam.label} style={{ position: "absolute", left: cam.x - 52, top: cam.y - 52, width: 104, height: 104, borderRadius: 52, display: "grid", placeItems: "center", background: c.deep, border: `3px solid ${cam.color}`, boxShadow: `0 0 40px ${alpha(cam.color, 0.6)}`, transform: `scale(${s})` }}>
              <Camera size={52} color={c.foreground} strokeWidth={2} />
              <div style={{ position: "absolute", top: 116, fontFamily: mono, fontSize: 22, color: cam.color, whiteSpace: "nowrap" }}>{cam.label}</div>
            </div>
          );
        })}
        <div style={{ position: "absolute", left: target.x - 470, top: target.y - 210, opacity: merged, transform: `translateY(${(1 - merged) * 20}px)`, fontFamily: mono, fontSize: 24, color: c.ok, padding: "10px 18px", borderRadius: 12, border: `2px solid ${c.ok}`, background: alpha(c.void, 0.8) }}>
          2 views → 1 tag · H05 SOLAR2
        </div>
        <AbsoluteFill style={{ top: 960, alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 24, opacity: callout, transform: `translateY(${(1 - callout) * 30}px)` }}>
            <span style={{ fontFamily: mono, fontSize: 30, color: c.muted, letterSpacing: "0.2em" }}>ANCHOR ERROR</span>
            <span style={{ ...display, fontSize: 72, fontWeight: 800 }}>8 to 20 mm</span>
          </div>
        </AbsoluteFill>
      </Backdrop>
    </Exit>
  );
}
