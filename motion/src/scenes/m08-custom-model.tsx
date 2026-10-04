import { Boxes, Cpu, Package } from "lucide-react";
import { AbsoluteFill, interpolate, random, useCurrentFrame } from "remotion";
import { Backdrop, Chars, clamp, display, easeInOut, easeOut, Exit, glass, Shine, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const nodes = [
  { Icon: Boxes, title: "9,000 renders", sub: "Blender, synthetic", color: c.primary },
  { Icon: Cpu, title: "training", sub: "YOLO detector", color: c.veo },
  { Icon: Package, title: "tagva-rex615", sub: "weights", color: c.ok },
];
const nodeW = 460;
const gap = 110;
const rowY = 330;

function Flow({ start }: { start: number }) {
  const frame = useCurrentFrame();
  const total = nodes.length * nodeW + (nodes.length - 1) * gap;
  const x0 = (1920 - total) / 2;
  return (
    <>
      {nodes.slice(0, -1).map((_, i) => {
        const x1 = x0 + (i + 1) * nodeW + i * gap;
        const draw = interpolate(frame, [start + 20 + i * 24, start + 40 + i * 24], [0, 1], { ...clamp, easing: easeInOut });
        return (
          <div key={i} style={{ position: "absolute", left: x1 + 10, top: rowY + 105, width: (gap - 20) * draw, height: 4, background: `linear-gradient(90deg, ${nodes[i].color}, ${nodes[i + 1].color})`, boxShadow: `0 0 16px ${nodes[i].color}` }}>
            {draw >= 1 &&
              Array.from({ length: 4 }, (_, k) => {
                const p = ((frame * 0.035 + k / 4 + random(`f${i}`)) % 1) * (gap - 20);
                return <div key={k} style={{ position: "absolute", left: p - 6, top: -5, width: 14, height: 14, borderRadius: 7, background: c.foreground, boxShadow: `0 0 14px 4px ${nodes[i + 1].color}` }} />;
              })}
          </div>
        );
      })}
      {nodes.map((n, i) => {
        const s = useSpring(start + i * 24, { damping: 12, stiffness: 120 });
        return (
          <div key={n.title} style={{ position: "absolute", left: x0 + i * (nodeW + gap), top: rowY, width: nodeW, height: 214, ...glass(n.color), display: "flex", alignItems: "center", gap: 24, padding: "0 32px", transform: `scale(${s}) translateY(${(1 - s) * 60}px)`, opacity: Math.min(1, s * 2), overflow: "hidden" }}>
            <div style={{ width: 92, height: 92, flexShrink: 0, borderRadius: 24, display: "grid", placeItems: "center", background: alpha(n.color, 0.16), border: `2px solid ${n.color}` }}>
              <n.Icon size={50} color={n.color} strokeWidth={2.1} />
            </div>
            <div>
              <div style={{ ...display, fontSize: i === 2 ? 36 : 44, fontWeight: 700, whiteSpace: "nowrap", ...(i === 2 && { fontFamily: mono, letterSpacing: "-0.02em" }) }}>{n.title}</div>
              <div style={{ fontFamily: mono, fontSize: 22, color: c.muted, marginTop: 10 }}>{n.sub}</div>
            </div>
            {i === 1 && <TrainingPulse start={start + 24} />}
            <Shine at={start + i * 24 + 14} duration={30} />
          </div>
        );
      })}
    </>
  );
}

function TrainingPulse({ start }: { start: number }) {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [start + 10, start + 120], [0, 1], { ...clamp, easing: easeOut });
  return <div style={{ position: "absolute", left: 0, bottom: 0, height: 6, width: `${p * 100}%`, background: `linear-gradient(90deg, ${c.primary}, ${c.veo})`, boxShadow: `0 0 14px ${c.veo}` }} />;
}

function Dial({ start }: { start: number }) {
  const frame = useCurrentFrame();
  const s = useSpring(start, { damping: 14 });
  const sweep = useSpring(start + 14, { damping: 7, stiffness: 50, mass: 1.2 });
  const value = 0.85 * sweep;
  const cx = 610;
  const cy = 330;
  const r = 250;
  const ang = (v: number) => Math.PI + v * Math.PI;
  const pt = (v: number, rr: number) => [cx + Math.cos(ang(v)) * rr, cy + Math.sin(ang(v)) * rr];
  const arc = (from: number, to: number, rr: number) => {
    const [x1, y1] = pt(from, rr);
    const [x2, y2] = pt(to, rr);
    return `M ${x1} ${y1} A ${rr} ${rr} 0 0 1 ${x2} ${y2}`;
  };
  const [nx, ny] = pt(value, r - 30);
  return (
    <div style={{ position: "absolute", left: 960 - 610, top: 590, width: 1220, height: 380, opacity: s, transform: `translateY(${(1 - s) * 80}px)` }}>
      <svg width={1220} height={380}>
        <path d={arc(0, 1, r)} stroke={alpha(c.border, 0.45)} strokeWidth={26} fill="none" strokeLinecap="round" />
        <path d={arc(0.85, 1, r)} stroke={alpha(c.ok, 0.35)} strokeWidth={26} fill="none" />
        {value > 0.001 && <path d={arc(0, value, r)} stroke="url(#dg)" strokeWidth={26} fill="none" strokeLinecap="round" style={{ filter: `drop-shadow(0 0 14px ${c.primary})` }} />}
        <defs>
          <linearGradient id="dg" x1="0" x2="1">
            <stop offset="0" stopColor={c.primary} />
            <stop offset="1" stopColor={c.ok} />
          </linearGradient>
        </defs>
        {Array.from({ length: 21 }, (_, i) => {
          const v = i / 20;
          const [a, b] = pt(v, r + 26);
          const [e, f] = pt(v, r + (i % 5 ? 40 : 56));
          return <line key={i} x1={a} y1={b} x2={e} y2={f} stroke={v <= value ? c.foreground : alpha(c.border, 0.8)} strokeWidth={3} />;
        })}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={c.foreground} strokeWidth={7} strokeLinecap="round" style={{ filter: `drop-shadow(0 0 10px ${c.primary})` }} />
        <circle cx={cx} cy={cy} r={18} fill={c.foreground} />
        <text x={cx} y={cy - 70} textAnchor="middle" fontFamily={mono} fontSize={96} fontWeight={700} fill={c.foreground}>
          {value.toFixed(2)}
        </text>
      </svg>
      <div style={{ position: "absolute", left: 930, top: 120, width: 420 }}>
        <div style={{ fontFamily: mono, fontSize: 22, letterSpacing: "0.24em", color: c.ok, fontWeight: 600 }}>CONFIDENCE FLOOR</div>
        <div style={{ ...display, fontSize: 40, fontWeight: 600, marginTop: 14, lineHeight: 1.15 }}>set on synthetic validation</div>
        <div style={{ fontFamily: mono, fontSize: 22, color: c.muted, marginTop: 14 }}>before any real result</div>
      </div>
    </div>
  );
}

export function M08CustomModel() {
  const frame = useCurrentFrame();
  const shift = interpolate(frame, [230, 270], [0, 1], { ...clamp, easing: easeInOut });
  const caption = useSpring(150, { damping: 16 });
  const glitch = frame < 30 && frame % 5 === 0 ? (random(`g${frame}`) - 0.5) * 24 : 0;
  return (
    <Exit>
      <Backdrop>
        <AbsoluteFill style={{ transform: `translateY(${shift * -150}px) scale(${1 - shift * 0.12})` }}>
          <AbsoluteFill style={{ alignItems: "center", top: 120 }}>
            <div style={{ ...display, fontSize: 130, fontWeight: 850, letterSpacing: "0.02em", transform: `translateX(${glitch}px)`, textShadow: `${-glitch / 3}px 0 ${c.veo}, ${glitch / 3}px 0 ${c.destructive}` }}>
              <Chars text="CUSTOM MODEL" delay={0} stagger={2} from={90} />
            </div>
          </AbsoluteFill>
          <Flow start={46} />
          <AbsoluteFill style={{ top: 600, alignItems: "center" }}>
            <div style={{ display: "flex", gap: 20, opacity: caption, transform: `translateY(${(1 - caption) * 20}px)` }}>
              {["YOLO", "single class", "1280 px", "renders only"].map((t, i) => (
                <span key={t} style={{ fontFamily: mono, fontSize: 30, padding: "10px 22px", borderRadius: 999, border: `1.5px solid ${alpha(c.primary, 0.6)}`, background: alpha(c.primary, 0.12), color: i === 3 ? c.review : c.foreground, opacity: interpolate(frame, [150 + i * 6, 160 + i * 6], [0, 1], clamp) }}>
                  {t}
                </span>
              ))}
            </div>
          </AbsoluteFill>
        </AbsoluteFill>
        <Dial start={250} />
      </Backdrop>
    </Exit>
  );
}
