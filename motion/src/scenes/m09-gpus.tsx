import { AbsoluteFill, Img, interpolate, random, staticFile, useCurrentFrame } from "remotion";
import { Backdrop, clamp, Count, display, Exit, glass, Shine, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const green = "#76B900";

function Gpu({ delay, x }: { delay: number; x: number }) {
  const frame = useCurrentFrame();
  const s = useSpring(delay, { damping: 13, stiffness: 100 });
  return (
    <div style={{ position: "absolute", left: x, top: 210, width: 560, height: 330, perspective: 1200 }}>
      <div style={{ position: "relative", width: "100%", height: "100%", ...glass(c.primary), borderColor: alpha(green, 0.6), boxShadow: `0 0 80px -10px ${alpha(green, 0.45)}`, transform: `rotateY(${(1 - s) * 70}deg) rotateX(${Math.sin(frame / 25 + delay) * 4}deg)`, opacity: Math.min(1, s * 2), overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 40, top: 40, width: 240, height: 240, borderRadius: 18, background: `linear-gradient(135deg, ${c.secondary}, ${c.deep})`, border: `2px solid ${alpha(green, 0.6)}`, display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: 5, padding: 16 }}>
          {Array.from({ length: 64 }, (_, i) => {
            const on = Math.sin(frame / 3 + random(`g${delay}${i}`) * 20) > 0.2;
            return <div key={i} style={{ borderRadius: 3, background: on ? green : alpha(green, 0.18), boxShadow: on ? `0 0 8px ${green}` : undefined }} />;
          })}
        </div>
        <div style={{ position: "absolute", left: 310, top: 46 }}>
          <Img src={staticFile("logos/nvidia-eye.svg")} style={{ height: 54 }} />
          <div style={{ ...display, fontSize: 64, fontWeight: 800, marginTop: 18 }}>A100</div>
          <div style={{ fontFamily: mono, fontSize: 22, color: c.muted, marginTop: 8 }}>80 GB · training</div>
        </div>
        <div style={{ position: "absolute", left: 310, right: 40, bottom: 52, display: "flex", gap: 6, alignItems: "flex-end", height: 60 }}>
          {Array.from({ length: 14 }, (_, i) => (
            <div key={i} style={{ flex: 1, borderRadius: 3, background: green, height: `${30 + 70 * Math.abs(Math.sin(frame / 6 + i * 0.7 + delay))}%`, opacity: 0.85 }} />
          ))}
        </div>
        <Shine at={delay + 20} duration={30} />
      </div>
    </div>
  );
}

export function M09Gpus() {
  const frame = useCurrentFrame();
  const head = useSpring(0, { damping: 16 });
  const stats = [
    { v: <Count to={3} start={50} end={70} />, l: "runs" },
    { v: <>&lt; 1 h</>, l: "each" },
    { v: <>≈ $<Count to={12} start={60} end={90} /></>, l: "of compute" },
  ];
  return (
    <Exit>
      <Backdrop>
        <AbsoluteFill style={{ alignItems: "center", top: 70 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 30, opacity: head, transform: `translateY(${(1 - head) * -30}px)` }}>
            <span style={{ ...display, fontSize: 72, fontWeight: 800 }}>2 ×</span>
            <Img src={staticFile("logos/nvidia-wordmark.svg")} style={{ height: 48 }} />
            <span style={{ ...display, fontSize: 72, fontWeight: 800 }}>A100</span>
            <span style={{ width: 2, height: 60, background: alpha(c.foreground, 0.3) }} />
            <span style={{ fontFamily: mono, fontSize: 26, color: c.muted }}>rented from</span>
            <Img src={staticFile("logos/verda-logo.svg")} style={{ height: 48 }} />
          </div>
        </AbsoluteFill>
        <Gpu delay={10} x={960 - 580} />
        <Gpu delay={18} x={960 + 20} />
        <AbsoluteFill style={{ top: 640, alignItems: "center" }}>
          <div style={{ display: "flex", gap: 40 }}>
            {stats.map((s, i) => {
              const sp = useSpring(46 + i * 10, { damping: 12, stiffness: 140 });
              return (
                <div key={s.l} style={{ width: 330, height: 200, ...glass(c.veo), display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", transform: `scale(${sp})`, opacity: interpolate(sp, [0, 0.4], [0, 1], clamp) }}>
                  <div style={{ ...display, fontSize: 92, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>{s.v}</div>
                  <div style={{ fontFamily: mono, fontSize: 24, color: c.muted, marginTop: 10 }}>{s.l}</div>
                </div>
              );
            })}
          </div>
        </AbsoluteFill>
      </Backdrop>
    </Exit>
  );
}
