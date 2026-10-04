import { AbsoluteFill, interpolate, random, useCurrentFrame } from "remotion";
import { Backdrop, clamp, Count, display, easeOut, Exit, useSpring, Words } from "../kit";
import { alpha, c, mono } from "../theme";

const land = 14;

export function M03Seventy() {
  const frame = useCurrentFrame();
  const s = useSpring(0, { damping: 9, stiffness: 110, mass: 1 });
  const scale = interpolate(s, [0, 1], [4.2, 1]);
  const shake = frame > land && frame < land + 12 ? (random(`k${frame}`) - 0.5) * 30 * (1 - (frame - land) / 12) : 0;
  const wave = interpolate(frame, [land, land + 34], [0, 1], { ...clamp, easing: easeOut });
  const ring = interpolate(frame, [8, 70], [0, 0.7], { ...clamp, easing: easeOut });
  const r = 330;
  const circ = 2 * Math.PI * r;

  return (
    <Exit>
      <Backdrop grid={false} glow={1.4}>
        <AbsoluteFill style={{ transform: `translate(${shake}px, ${shake * 0.6}px)` }}>
          <svg width={1920} height={1080} style={{ position: "absolute" }}>
            <defs>
              <linearGradient id="g70" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0" stopColor={c.primary} />
                <stop offset="1" stopColor={c.veo} />
              </linearGradient>
            </defs>
            <circle cx={960} cy={460} r={r} fill="none" stroke={alpha(c.border, 0.35)} strokeWidth={22} />
            <circle
              cx={960}
              cy={460}
              r={r}
              fill="none"
              stroke="url(#g70)"
              strokeWidth={22}
              strokeLinecap="round"
              strokeDasharray={`${circ * ring} ${circ}`}
              transform="rotate(-90 960 460)"
              style={{ filter: `drop-shadow(0 0 22px ${c.primary})` }}
            />
            {Array.from({ length: 60 }, (_, i) => {
              const a = (i / 60) * Math.PI * 2 - Math.PI / 2;
              const on = i / 60 < ring;
              return <line key={i} x1={960 + Math.cos(a) * 370} y1={460 + Math.sin(a) * 370} x2={960 + Math.cos(a) * (i % 5 ? 385 : 400)} y2={460 + Math.sin(a) * (i % 5 ? 385 : 400)} stroke={on ? c.veo : alpha(c.border, 0.5)} strokeWidth={3} />;
            })}
            <circle cx={960} cy={460} r={200 + wave * 900} fill="none" stroke={c.foreground} strokeWidth={6 * (1 - wave)} opacity={1 - wave} />
            {Array.from({ length: 28 }, (_, i) => {
              const a = random(`a${i}`) * Math.PI * 2;
              const d = 180 + wave * (300 + random(`d${i}`) * 500);
              return <circle key={i} cx={960 + Math.cos(a) * d} cy={460 + Math.sin(a) * d} r={3 + random(`r${i}`) * 5} fill={i % 2 ? c.primary : c.veo} opacity={frame > land ? 1 - wave : 0} />;
            })}
          </svg>
          <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", top: -120 }}>
            <div style={{ ...display, fontSize: 220, fontWeight: 800, display: "flex", alignItems: "baseline", transform: `scale(${scale})`, opacity: Math.min(1, s * 3), filter: `blur(${Math.max(0, 1 - s) * 30}px)`, textShadow: `0 0 80px ${alpha(c.primary, 0.6)}` }}>
              <span style={{ color: c.veo, fontWeight: 500, marginRight: 14 }}>≈</span>
              <span style={{ fontVariantNumeric: "tabular-nums" }}>
                <Count to={70} start={0} end={land + 4} />
              </span>
              <span style={{ fontSize: 130, marginLeft: 18, color: c.primary }}>%</span>
            </div>
          </AbsoluteFill>
        </AbsoluteFill>
        <AbsoluteFill style={{ top: 900, alignItems: "center", gap: 22 }}>
          <Words text="less manual work" delay={32} style={{ ...display, fontSize: 64, fontWeight: 600 }} />
          <div style={{ fontFamily: mono, fontSize: 26, color: c.muted, letterSpacing: "0.08em", opacity: interpolate(frame, [52, 70], [0, 1], clamp) }}>
            VEO's estimate, challenge presentation
          </div>
        </AbsoluteFill>
      </Backdrop>
    </Exit>
  );
}
