import { Lock, LockOpen } from "lucide-react";
import { AbsoluteFill, Img, interpolate, random, staticFile, useCurrentFrame, useVideoConfig, spring } from "remotion";
import { Backdrop, clamp, Count, display, easeInOut, Exit, glass, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const cols = 23;
const cell = 54;
const gap = 7;
const n = 206;
const gridW = cols * (cell + gap) - gap;
const gridH = Math.ceil(n / cols) * (cell + gap) - gap;
const gx = (1920 - gridW) / 2;
const gy = 150;
const lockAt = 96;
const rule = 220;

function Tiles() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      {Array.from({ length: n }, (_, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        const d = 4 + (col + row) * 1.6 + random(`d${i}`) * 6;
        const s = spring({ frame: frame - d, fps, config: { damping: 15, stiffness: 120 } });
        const fx = (random(`x${i}`) - 0.5) * 2600;
        const fy = (random(`y${i}`) - 0.5) * 1600;
        const locked = interpolate(frame, [lockAt, lockAt + 10], [0, 1], clamp);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: gx + col * (cell + gap),
              top: gy + row * (cell + gap),
              width: cell,
              height: cell,
              borderRadius: 7,
              overflow: "hidden",
              transform: `translate(${(1 - s) * fx}px, ${(1 - s) * fy}px) rotate(${(1 - s) * 180}deg) scale(${0.4 + 0.6 * s})`,
              opacity: Math.min(1, s * 1.5),
              border: `1.5px solid ${locked ? alpha(c.review, 0.5 * locked) : alpha(c.border, 0.4)}`,
            }}
          >
            <Img src={staticFile(`img/real/r-${i % 48}.jpg`)} style={{ width: "100%", height: "100%", objectFit: "cover", filter: `saturate(${1 - 0.6 * locked}) brightness(${1 - 0.35 * locked})` }} />
          </div>
        );
      })}
    </>
  );
}

export function M11HeldOut() {
  const frame = useCurrentFrame();
  const drop = useSpring(lockAt - 22, { damping: 10, stiffness: 140 });
  const click = interpolate(frame, [lockAt, lockAt + 4, lockAt + 22], [0, 1, 0], clamp);
  const cage = interpolate(frame, [lockAt - 4, lockAt + 24], [0, 1], { ...clamp, easing: easeInOut });
  const stats = useSpring(lockAt + 14, { damping: 15 });
  const up = interpolate(frame, [rule - 10, rule + 20], [0, 1], { ...clamp, easing: easeInOut });
  const card = useSpring(rule + 6, { damping: 14 });
  const typed = "Pass = every relay found, ≤ 1 false positive";
  const k = Math.max(0, Math.min(typed.length, Math.floor((frame - rule - 12) * 1.4)));
  const locked = frame >= lockAt;
  const LockIcon = locked ? Lock : LockOpen;
  const perim = 2 * (gridW + gridH + 60);

  return (
    <Exit>
      <Backdrop>
        <AbsoluteFill style={{ transform: `translateY(${-up * 70}px) scale(${1 - up * 0.18})`, filter: `blur(${up * 3}px)`, opacity: 1 - up * 0.45 }}>
          <Tiles />
          <svg width={1920} height={1080} style={{ position: "absolute" }}>
            <rect x={gx - 30} y={gy - 30} width={gridW + 60} height={gridH + 60} rx={26} fill={alpha(c.review, 0.05 * cage)} stroke={c.review} strokeWidth={4} strokeDasharray={`${perim * cage} ${perim}`} style={{ filter: `drop-shadow(0 0 14px ${c.review})` }} />
          </svg>
          <div style={{ position: "absolute", left: 960 - 95, top: gy + gridH / 2 - 95, width: 190, height: 190, borderRadius: 48, display: "grid", placeItems: "center", background: alpha(c.void, 0.88), border: `4px solid ${c.review}`, boxShadow: `0 0 ${60 + click * 120}px ${alpha(c.review, 0.5 + click * 0.5)}`, transform: `translateY(${(1 - drop) * -700}px) scale(${1 + click * 0.15})`, opacity: Math.min(1, drop * 3) }}>
            <LockIcon size={108} color={c.review} strokeWidth={2.2} />
          </div>
          <AbsoluteFill style={{ top: gy + gridH + 70, alignItems: "center", gap: 20, opacity: stats, transform: `translateY(${(1 - stats) * 30}px)` }}>
            <div style={{ ...display, fontSize: 70, fontWeight: 750, display: "flex", gap: 30, fontVariantNumeric: "tabular-nums" }}>
              <span>
                <Count to={206} start={lockAt + 14} end={lockAt + 50} /> real tiles
              </span>
              <span style={{ color: c.primary }}>·</span>
              <span>
                <Count to={251} start={lockAt + 20} end={lockAt + 56} /> relay boxes
              </span>
            </div>
            <div style={{ fontFamily: mono, fontSize: 32, color: c.review, letterSpacing: "0.06em" }}>never used for training</div>
          </AbsoluteFill>
        </AbsoluteFill>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-end", paddingBottom: 110 }}>
          <div style={{ ...glass(c.ok), padding: "40px 64px", transform: `translateY(${(1 - card) * 200}px) scale(${0.9 + 0.1 * card})`, opacity: card, display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ fontFamily: mono, fontSize: 22, letterSpacing: "0.3em", color: c.ok, fontWeight: 600 }}>ACCEPTANCE RULE, FIXED IN ADVANCE</div>
            <div style={{ fontFamily: mono, fontSize: 54, fontWeight: 700, color: c.foreground }}>
              {typed.slice(0, k)}
              <span style={{ color: c.ok, opacity: Math.floor(frame / 8) % 2 ? 1 : 0 }}>▍</span>
            </div>
          </div>
        </AbsoluteFill>
      </Backdrop>
    </Exit>
  );
}
