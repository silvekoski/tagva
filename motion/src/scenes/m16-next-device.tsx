import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Backdrop, clamp, display, easeInOut, Exit, useSpring, Words } from "../kit";
import { alpha, c, mono } from "../theme";

const plateW = 300;
const plateH = plateW / (2048 / 1383);
const slots = [
  { w: 1, h: 1 },
  { w: 0.62, h: 1.25 },
  { w: 1.1, h: 0.8 },
  { w: 0.8, h: 1.1 },
  { w: 1.2, h: 1 },
];
const gap = 48;
const rowY = 400;
const morph = 40;

function Silhouette({ w, h, i }: { w: number; h: number; i: number }) {
  const frame = useCurrentFrame();
  const s = useSpring(morph + 14 + i * 9, { damping: 13, stiffness: 120 });
  const dash = -frame * 1.2;
  const W = plateW * w;
  const H = plateH * h;
  return (
    <div style={{ position: "relative", width: W, height: H, transform: `translateX(${(1 - s) * -(i * (plateW + gap))}px) scale(${0.6 + 0.4 * s})`, opacity: s }}>
      <svg width={W} height={H} style={{ position: "absolute", overflow: "visible" }}>
        <rect x={2} y={2} width={W - 4} height={H - 4} rx={14} fill={alpha(c.primary, 0.06)} stroke={c.primary} strokeWidth={3} strokeDasharray="12 9" strokeDashoffset={dash} />
        <rect x={W * 0.14} y={H * 0.16} width={W * 0.34} height={H * 0.32} rx={6} fill="none" stroke={alpha(c.primary, 0.7)} strokeWidth={2.5} strokeDasharray="8 6" strokeDashoffset={dash} />
        {Array.from({ length: 6 }, (_, k) => (
          <circle key={k} cx={W * 0.62 + (k % 3) * W * 0.1} cy={H * 0.24 + Math.floor(k / 3) * H * 0.16} r={Math.max(5, W * 0.025)} fill="none" stroke={alpha(c.primary, 0.7)} strokeWidth={2.5} />
        ))}
        {Array.from({ length: 4 }, (_, k) => (
          <rect key={k} x={W * 0.14 + k * W * 0.19} y={H * 0.68} width={W * 0.13} height={H * 0.12} rx={4} fill="none" stroke={alpha(c.primary, 0.6)} strokeWidth={2} />
        ))}
      </svg>
      <div style={{ position: "absolute", top: H + 18, width: "100%", textAlign: "center", fontFamily: mono, fontSize: 20, color: c.muted, letterSpacing: "0.12em" }}>next device</div>
    </div>
  );
}

export function M16NextDevice() {
  const frame = useCurrentFrame();
  const enter = useSpring(0, { damping: 14, stiffness: 90 });
  const move = interpolate(frame, [26, morph + 10], [0, 1], { ...clamp, easing: easeInOut });
  const rowW = slots.reduce((a, s) => a + plateW * s.w, 0) + gap * (slots.length - 1);
  const rowX = (1920 - rowW) / 2;
  const startScale = 2.1;
  const scale = startScale + (1 - startScale) * move;
  const cx = 960 + (rowX + plateW / 2 - 960) * move;
  const cy = 470 + (rowY + plateH / 2 - 470) * move;

  return (
    <Exit>
      <Backdrop>
        <div style={{ position: "absolute", left: rowX, top: rowY + plateH / 2, display: "flex", alignItems: "center", gap, transform: "translateY(-50%)" }}>
          <div style={{ width: plateW, height: plateH }} />
          {slots.slice(1).map((s, i) => (
            <Silhouette key={i} w={s.w} h={s.h} i={i} />
          ))}
        </div>
        <div style={{ position: "absolute", left: cx - plateW / 2, top: cy - plateH / 2, width: plateW, height: plateH, transform: `scale(${scale * (0.6 + 0.4 * enter)}) rotateY(${(1 - enter) * 50}deg)`, opacity: enter, filter: `drop-shadow(0 0 ${30 + 30 * (1 - move)}px ${alpha(c.primary, 0.6)})` }}>
          <Img src={staticFile("img/rex615-front.png")} style={{ width: "100%", height: "100%", borderRadius: 8 }} />
          <div style={{ position: "absolute", top: plateH + 18, width: "100%", textAlign: "center", fontFamily: mono, fontSize: 20 / (scale * (0.6 + 0.4 * enter)), color: c.ok, letterSpacing: "0.12em", opacity: move }}>REX615</div>
        </div>
        <AbsoluteFill style={{ top: 800, alignItems: "center" }}>
          <Words text="1 front plate · 1 GPU-hour" delay={110} style={{ ...display, fontSize: 80, fontWeight: 750 }} wordStyle={(i) => (i === 3 || i === 4 ? { color: c.veo } : i === 2 ? { color: c.primary } : {})} />
        </AbsoluteFill>
      </Backdrop>
    </Exit>
  );
}
