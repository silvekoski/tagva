import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { alpha, brand, c, mono, sans } from "./theme";

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
export const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);

export function useSpring(delay = 0, config: { damping?: number; stiffness?: number; mass?: number } = {}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping: 14, stiffness: 120, mass: 0.8, ...config } });
}

export function useTween(from: number, to: number, ease = easeOut) {
  const frame = useCurrentFrame();
  return interpolate(frame, [from, to], [0, 1], { ...clamp, easing: ease });
}

export const logos = {
  tagva: { src: "logos/tagva-logo.svg", ratio: 1692 / 579 },
  veo: { src: "logos/veo-logo.svg", ratio: 171.532 / 36.954 },
} as const;

export function Logo({ name, height, fill = c.foreground, style }: { name: keyof typeof logos; height: number; fill?: string; style?: CSSProperties }) {
  const { src, ratio } = logos[name];
  const mask = `url("${staticFile(src)}") center / contain no-repeat`;
  return (
    <div
      role="img"
      aria-label={name === "tagva" ? "Tagva" : "VEO"}
      style={{ height, width: height * ratio, background: fill, mask, WebkitMask: mask, ...style }}
    />
  );
}

export function Backdrop({ grid = true, glow = 1, children }: { grid?: boolean; glow?: number; children?: ReactNode }) {
  const frame = useCurrentFrame();
  const t = frame / 30;
  const ax = 30 + Math.sin(t * 0.5) * 12;
  const ay = 30 + Math.cos(t * 0.4) * 10;
  const bx = 72 + Math.cos(t * 0.35) * 12;
  const by = 70 + Math.sin(t * 0.45) * 10;
  return (
    <AbsoluteFill style={{ background: c.void, overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(60% 70% at ${ax}% ${ay}%, ${alpha(c.chart3, 0.42 * glow)}, transparent 70%),
            radial-gradient(55% 60% at ${bx}% ${by}%, ${alpha(c.veo, 0.28 * glow)}, transparent 70%),
            radial-gradient(120% 90% at 50% 40%, ${c.background}, ${c.void} 75%)`,
        }}
      />
      {grid && <GridFloor />}
      <Particles />
      <AbsoluteFill style={{ background: `radial-gradient(90% 80% at 50% 50%, transparent 55%, ${alpha(c.void, 0.85)})` }} />
      {children}
    </AbsoluteFill>
  );
}

export function GridFloor({ speed = 1, opacity = 1 }: { speed?: number; opacity?: number }) {
  const frame = useCurrentFrame();
  const shift = (frame * 2.2 * speed) % 80;
  const line = alpha(c.primary, 0.35);
  return (
    <AbsoluteFill style={{ perspective: 900, perspectiveOrigin: "50% 30%", opacity }}>
      <div
        style={{
          position: "absolute",
          left: "-60%",
          width: "220%",
          top: "52%",
          height: "140%",
          transform: "rotateX(76deg)",
          transformOrigin: "50% 0%",
          backgroundImage: `linear-gradient(${line} 1.5px, transparent 1.5px), linear-gradient(90deg, ${line} 1.5px, transparent 1.5px)`,
          backgroundSize: "80px 80px",
          backgroundPosition: `0 ${shift}px`,
          maskImage: "linear-gradient(to bottom, transparent 0%, black 25%, black 55%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, black 25%, black 55%, transparent 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: "50%",
          height: 3,
          background: `linear-gradient(90deg, transparent, ${alpha(c.primary, 0.9)}, ${alpha(c.veo, 0.9)}, transparent)`,
          filter: "blur(2px)",
          boxShadow: `0 0 40px 8px ${alpha(c.primary, 0.35)}`,
        }}
      />
    </AbsoluteFill>
  );
}

export function Particles({ count = 70, seed = "p" }: { count?: number; seed?: string }) {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  return (
    <AbsoluteFill>
      {Array.from({ length: count }, (_, i) => {
        const x = random(`${seed}x${i}`) * width;
        const sp = 0.3 + random(`${seed}s${i}`) * 1.2;
        const y = (random(`${seed}y${i}`) * (height + 100) - frame * sp + height * 4) % (height + 100) - 50;
        const r = 1 + random(`${seed}r${i}`) * 2.6;
        const tw = 0.35 + 0.65 * Math.abs(Math.sin(frame / (14 + random(`${seed}t${i}`) * 30) + i));
        const col = random(`${seed}c${i}`) > 0.5 ? c.primary : c.veo;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x + Math.sin(frame / 40 + i) * 14,
              top: y,
              width: r,
              height: r,
              borderRadius: r,
              background: col,
              opacity: tw * 0.75,
              boxShadow: `0 0 ${r * 5}px ${col}`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
}

export function Chars({
  text,
  delay = 0,
  stagger = 1.6,
  style,
  from = 60,
  blur = 16,
}: {
  text: string;
  delay?: number;
  stagger?: number;
  style?: CSSProperties;
  from?: number;
  blur?: number;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <span style={{ display: "inline-block", whiteSpace: "pre", ...style }}>
      {[...text].map((ch, i) => {
        const s = spring({ frame: frame - delay - i * stagger, fps, config: { damping: 15, stiffness: 140, mass: 0.7 } });
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              opacity: interpolate(s, [0, 0.6], [0, 1], clamp),
              transform: `translateY(${(1 - s) * from}px) rotateX(${(1 - s) * 70}deg)`,
              filter: `blur(${(1 - Math.min(1, s)) * blur}px)`,
            }}
          >
            {ch}
          </span>
        );
      })}
    </span>
  );
}

export function Words({ text, delay = 0, stagger = 4, style, wordStyle }: { text: string; delay?: number; stagger?: number; style?: CSSProperties; wordStyle?: (i: number) => CSSProperties }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <span style={{ display: "inline-flex", flexWrap: "wrap", justifyContent: "center", columnGap: "0.28em", ...style }}>
      {text.split(" ").map((w, i) => {
        const s = spring({ frame: frame - delay - i * stagger, fps, config: { damping: 16, stiffness: 150 } });
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              opacity: interpolate(s, [0, 0.5], [0, 1], clamp),
              transform: `translateY(${(1 - s) * 40}px) scale(${0.9 + 0.1 * s})`,
              filter: `blur(${(1 - Math.min(1, s)) * 12}px)`,
              ...wordStyle?.(i),
            }}
          >
            {w}
          </span>
        );
      })}
    </span>
  );
}

export function Brackets({
  w,
  h,
  color = c.ok,
  progress = 1,
  thickness = 4,
  arm = 0.28,
  glow = true,
}: {
  w: number;
  h: number;
  color?: string;
  progress?: number;
  thickness?: number;
  arm?: number;
  glow?: boolean;
}) {
  const a = Math.max(10, Math.min(w, h) * arm) * Math.min(1, progress);
  const common: CSSProperties = { position: "absolute", width: a, height: a, borderColor: color, borderStyle: "solid", borderWidth: 0 };
  return (
    <div style={{ position: "absolute", inset: 0, filter: glow ? `drop-shadow(0 0 8px ${color})` : undefined, opacity: Math.min(1, progress * 3) }}>
      <div style={{ ...common, left: 0, top: 0, borderLeftWidth: thickness, borderTopWidth: thickness }} />
      <div style={{ ...common, right: 0, top: 0, borderRightWidth: thickness, borderTopWidth: thickness }} />
      <div style={{ ...common, left: 0, bottom: 0, borderLeftWidth: thickness, borderBottomWidth: thickness }} />
      <div style={{ ...common, right: 0, bottom: 0, borderRightWidth: thickness, borderBottomWidth: thickness }} />
      <div style={{ position: "absolute", inset: 0, border: `1.5px solid ${color}`, opacity: 0.35 * progress, borderRadius: 2 }} />
    </div>
  );
}

export function Exit({ duration = 14, children, style }: { duration?: number; children: ReactNode; style?: CSSProperties }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const t = interpolate(frame, [durationInFrames - duration, durationInFrames - 1], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
  return (
    <AbsoluteFill style={{ opacity: 1 - t, transform: `scale(${1 + t * 0.06})`, filter: `blur(${t * 14}px)`, ...style }}>{children}</AbsoluteFill>
  );
}

export function Drift({ children, amount = 0.05 }: { children: ReactNode; amount?: number }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const t = frame / durationInFrames;
  return <AbsoluteFill style={{ transform: `scale(${1 + amount * t}) translateY(${-t * 10}px)` }}>{children}</AbsoluteFill>;
}

export const glass = (accent: string = c.primary): CSSProperties => ({
  background: `linear-gradient(160deg, ${alpha(c.card, 0.78)}, ${alpha(c.deep, 0.72)})`,
  border: `1.5px solid ${alpha(accent, 0.45)}`,
  borderRadius: 28,
  boxShadow: `0 30px 80px -20px ${alpha(c.void, 0.9)}, 0 0 60px -10px ${alpha(accent, 0.35)}, inset 0 1px 0 ${alpha(c.foreground, 0.12)}`,
  backdropFilter: "blur(18px)",
});

export function Shine({ at, duration = 30, angle = 105, strength = 0.5 }: { at: number; duration?: number; angle?: number; strength?: number }) {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + duration], [-30, 130], { ...clamp, easing: easeInOut });
  if (frame < at || frame > at + duration) return null;
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        mixBlendMode: "overlay",
        background: `linear-gradient(${angle}deg, transparent ${p - 12}%, ${alpha(c.foreground, strength)} ${p}%, transparent ${p + 12}%)`,
      }}
    />
  );
}

export function Count({ from = 0, to, start, end, decimals = 0, ease = easeOut }: { from?: number; to: number; start: number; end: number; decimals?: number; ease?: (t: number) => number }) {
  const frame = useCurrentFrame();
  const v = interpolate(frame, [start, end], [from, to], { ...clamp, easing: ease });
  return <>{v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}</>;
}

export function Kicker({ children, color = c.primary, delay = 0 }: { children: ReactNode; color?: string; delay?: number }) {
  const s = useSpring(delay, { damping: 18 });
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 14,
        fontFamily: mono,
        fontSize: 28,
        fontWeight: 600,
        letterSpacing: "0.28em",
        textTransform: "uppercase",
        color,
        opacity: s,
        transform: `translateX(${(1 - s) * -40}px)`,
      }}
    >
      <div style={{ width: 46 * s, height: 3, background: color, boxShadow: `0 0 12px ${color}` }} />
      {children}
    </div>
  );
}

export const brandText: CSSProperties = {
  backgroundImage: brand,
  WebkitBackgroundClip: "text",
  backgroundClip: "text",
  color: "transparent",
};

export const display: CSSProperties = { fontFamily: sans, color: c.foreground, letterSpacing: "-0.035em", lineHeight: 1 };

export function ScanSweep({ at, duration = 40, color = c.veo, vertical = false }: { at: number; duration?: number; color?: string; vertical?: boolean }) {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + duration], [-10, 110], { ...clamp, easing: easeInOut });
  if (frame < at || frame > at + duration) return null;
  const line: CSSProperties = vertical
    ? { left: 0, right: 0, top: `${p}%`, height: 3, boxShadow: `0 0 30px 10px ${alpha(color, 0.6)}, 0 -120px 120px -60px ${alpha(color, 0.25)}` }
    : { top: 0, bottom: 0, left: `${p}%`, width: 3, boxShadow: `0 0 30px 10px ${alpha(color, 0.6)}, -140px 0 140px -70px ${alpha(color, 0.25)}` };
  return <div style={{ position: "absolute", background: color, ...line }} />;
}
