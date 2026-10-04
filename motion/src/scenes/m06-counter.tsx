import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import data from "../data.json";
import { clamp, display, easeInOut, Exit, Kicker, Particles, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const cols = 12;
const rows = 7;
const cell = 230;
const segs = [
  { n: 6000, label: "base", color: c.primary },
  { n: 1500, label: "dark", color: c.chart3 },
  { n: 1500, label: "occluded", color: c.veo },
];

function Wall() {
  const frame = useCurrentFrame();
  const shift = frame * 1.6;
  return (
    <AbsoluteFill style={{ perspective: 1600, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: -500, top: -260, width: cols * cell, height: rows * cell, transform: `rotateX(18deg) rotateY(-22deg) rotateZ(4deg) translateX(${-shift}px)`, transformOrigin: "50% 50%" }}>
        {Array.from({ length: cols * rows }, (_, i) => {
          const t = data.thumbs[(i * 7) % data.thumbs.length];
          const col = i % cols;
          const row = Math.floor(i / cols);
          const at = 6 + ((col * 5 + row * 11) % 60);
          const pop = interpolate(frame, [at, at + 6], [0, 1], clamp);
          return (
            <div key={i} style={{ position: "absolute", left: col * cell, top: row * cell, width: cell - 14, height: cell - 14, borderRadius: 12, overflow: "hidden", border: `1.5px solid ${alpha(c.border, 0.5)}` }}>
              <Img src={staticFile(t.src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              {t.boxes.map((b, j) => (
                <div
                  key={j}
                  style={{
                    position: "absolute",
                    left: `${(b[0] - b[2] / 2) * 100}%`,
                    top: `${(b[1] - b[3] / 2) * 100}%`,
                    width: `${b[2] * 100}%`,
                    height: `${b[3] * 100}%`,
                    border: `2.5px solid ${c.ok}`,
                    boxShadow: `0 0 12px ${c.ok}`,
                    opacity: pop,
                    transform: `scale(${1.8 - 0.8 * pop})`,
                  }}
                />
              ))}
              <div style={{ position: "absolute", inset: 0, background: c.ok, opacity: (1 - pop) * (pop > 0 ? 0.5 : 0) }} />
            </div>
          );
        })}
      </div>
      <AbsoluteFill style={{ background: `radial-gradient(70% 70% at 50% 50%, ${alpha(c.void, 0.92)} 30%, ${alpha(c.void, 0.55)} 100%)` }} />
    </AbsoluteFill>
  );
}

export function M06Counter() {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [12, 120], [0, 1], { ...clamp, easing: easeInOut });
  const total = 9000;
  const barW = 1300;
  const cap = useSpring(118, { damping: 16 });
  const pulse = interpolate(frame, [120, 128, 150], [1, 1.06, 1], clamp);

  let acc = 0;
  return (
    <Exit>
      <AbsoluteFill style={{ background: c.void }}>
        <Wall />
        <Particles count={40} />
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 36 }}>
          <Kicker color={c.veo}>Synthetic training set</Kicker>
          <div style={{ ...display, fontSize: 250, fontWeight: 800, fontVariantNumeric: "tabular-nums", transform: `scale(${pulse})`, textShadow: `0 0 70px ${alpha(c.primary, 0.6)}` }}>
            {Math.round(total * p).toLocaleString("en-US")}
          </div>
          <div style={{ position: "relative", width: barW, height: 34, borderRadius: 17, background: alpha(c.secondary, 0.7), overflow: "hidden", border: `1.5px solid ${alpha(c.border, 0.6)}` }}>
            {segs.map((s) => {
              const left = acc / total;
              acc += s.n;
              const w = Math.max(0, Math.min(s.n / total, p - left));
              return <div key={s.label} style={{ position: "absolute", left: left * barW, top: 0, bottom: 0, width: w * barW, background: s.color, boxShadow: `0 0 26px ${s.color}`, borderRight: `3px solid ${c.void}` }} />;
            })}
          </div>
          <div style={{ position: "relative", width: barW, height: 80 }}>
            {(() => {
              let a = 0;
              return segs.map((s) => {
                const left = a / total;
                a += s.n;
                const on = interpolate(p, [left, left + 0.06], [0, 1], clamp);
                return (
                  <div key={s.label} style={{ position: "absolute", left: left * barW, width: (s.n / total) * barW, opacity: on, transform: `translateY(${(1 - on) * 20}px)`, fontFamily: mono, display: "flex", flexDirection: "column", alignItems: s.label === "base" ? "flex-start" : "center" }}>
                    <span style={{ fontSize: 36, fontWeight: 700, color: s.color }}>{s.n.toLocaleString("en-US")}</span>
                    <span style={{ fontSize: 22, color: c.muted }}>{s.label}</span>
                  </div>
                );
              });
            })()}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 20, opacity: cap, transform: `translateY(${(1 - cap) * 30}px)`, marginTop: 10 }}>
            <Img src={staticFile("logos/blender-logo.svg")} style={{ height: 52 }} />
            <span style={{ ...display, fontSize: 46, fontWeight: 500, letterSpacing: "-0.01em" }}>
              labeled by Blender, <span style={{ color: c.review }}>not by a person</span>
            </span>
          </div>
        </AbsoluteFill>
      </AbsoluteFill>
    </Exit>
  );
}
