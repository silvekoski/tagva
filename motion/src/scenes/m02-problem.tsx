import { FileText, MapPin, Search } from "lucide-react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { evolvePath } from "@remotion/paths";
import { Backdrop, clamp, display, easeInOut, Exit, glass, Kicker, Shine, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const tiles = [
  { n: "01", label: "Find", Icon: Search, color: c.primary },
  { n: "02", label: "Name", Icon: MapPin, color: c.veo },
  { n: "03", label: "Link", Icon: FileText, color: c.browser },
];
const tileW = 440;
const gap = 70;

function FindDemo({ t }: { t: number }) {
  const frame = useCurrentFrame();
  const x = 50 + Math.sin(frame / 14) * 34;
  const y = 50 + Math.cos(frame / 19) * 26;
  return (
    <div style={{ position: "relative", width: 300, height: 130, borderRadius: 14, overflow: "hidden", background: alpha(c.void, 0.6), opacity: t }}>
      {Array.from({ length: 24 }, (_, i) => (
        <div key={i} style={{ position: "absolute", left: 18 + (i % 8) * 36, top: 20 + Math.floor(i / 8) * 34, width: 22, height: 18, borderRadius: 4, background: alpha(c.border, 0.6) }} />
      ))}
      <div style={{ position: "absolute", left: `${x}%`, top: `${y}%`, width: 70, height: 70, transform: "translate(-50%, -50%)", borderRadius: 35, border: `3px solid ${c.primary}`, background: alpha(c.primary, 0.15), boxShadow: `0 0 24px ${c.primary}` }} />
    </div>
  );
}

function NameDemo({ t, start }: { t: number; start: number }) {
  const frame = useCurrentFrame();
  const text = "H05 SOLAR2";
  const cycle = Math.max(0, frame - start) % 70;
  const n = Math.min(text.length, Math.floor(cycle / 3.2));
  return (
    <div style={{ width: 300, height: 130, borderRadius: 14, background: alpha(c.void, 0.6), display: "flex", alignItems: "center", justifyContent: "center", opacity: t }}>
      <div style={{ fontFamily: mono, fontSize: 38, fontWeight: 600, color: c.foreground, padding: "10px 18px", border: `2px solid ${alpha(c.veo, 0.7)}`, borderRadius: 10 }}>
        {text.slice(0, n)}
        <span style={{ opacity: Math.floor(frame / 8) % 2 ? 1 : 0, color: c.veo }}>▍</span>
      </div>
    </div>
  );
}

function LinkDemo({ t, start }: { t: number; start: number }) {
  const frame = useCurrentFrame();
  const cycle = (Math.max(0, frame - start) % 60) / 60;
  const path = "M 70 65 C 120 10, 180 120, 230 65";
  const { strokeDasharray, strokeDashoffset } = evolvePath(interpolate(cycle, [0, 0.6], [0, 1], { ...clamp, easing: easeInOut }), path);
  return (
    <div style={{ position: "relative", width: 300, height: 130, borderRadius: 14, background: alpha(c.void, 0.6), opacity: t }}>
      <svg width={300} height={130} style={{ position: "absolute" }}>
        <path d={path} fill="none" stroke={c.browser} strokeWidth={4} strokeLinecap="round" strokeDasharray={strokeDasharray} strokeDashoffset={strokeDashoffset} style={{ filter: `drop-shadow(0 0 6px ${c.browser})` }} />
      </svg>
      <MapPin size={50} color={c.foreground} strokeWidth={2.2} style={{ position: "absolute", left: 22, top: 40 }} />
      <FileText size={54} color={c.browser} strokeWidth={2.2} style={{ position: "absolute", left: 222, top: 38 }} />
    </div>
  );
}

export function M02Problem() {
  const frame = useCurrentFrame();
  const totalW = tiles.length * tileW + (tiles.length - 1) * gap;
  const loop = frame > 120 ? Math.floor((frame - 120) / Math.max(6, 22 - (frame - 120) / 10)) % 3 : -1;
  const under = useSpring(150, { damping: 18 });
  const segs = ["18 panoramas", "every device", "by hand"];
  const ul = interpolate(frame, [200, 228], [0, 1], { ...clamp, easing: easeInOut });
  const ulPath = "M 4 14 C 80 4, 180 22, 300 8";
  const ulEvo = evolvePath(ul, ulPath);

  return (
    <Exit>
      <Backdrop>
        <AbsoluteFill style={{ alignItems: "center", paddingTop: 120 }}>
          <Kicker color={c.review} delay={2}>
            The manual work today
          </Kicker>
        </AbsoluteFill>
        <AbsoluteFill style={{ perspective: 1400 }}>
          {tiles.map((tile, i) => {
            const d = 12 + i * 14;
            const s = useSpring(d, { damping: 13, stiffness: 90 });
            const active = loop === i;
            const left = (1920 - totalW) / 2 + i * (tileW + gap);
            const demo = interpolate(frame, [d + 20, d + 40], [0, 1], clamp);
            return (
              <div
                key={tile.n}
                style={{
                  position: "absolute",
                  left,
                  top: 270,
                  width: tileW,
                  height: 470,
                  ...glass(tile.color),
                  borderColor: active ? tile.color : alpha(tile.color, 0.4),
                  boxShadow: active ? `0 0 90px -5px ${alpha(tile.color, 0.7)}` : glass(tile.color).boxShadow,
                  transform: `translateY(${(1 - s) * 520}px) rotateX(${(1 - s) * -55}deg) scale(${active ? 1.035 : 1})`,
                  opacity: interpolate(s, [0, 0.3], [0, 1], clamp),
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "44px 0 52px",
                  overflow: "hidden",
                }}
              >
                <div style={{ width: "100%", padding: "0 40px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ width: 84, height: 84, borderRadius: 22, display: "grid", placeItems: "center", background: alpha(tile.color, 0.16), border: `2px solid ${alpha(tile.color, 0.6)}` }}>
                    <tile.Icon size={46} color={tile.color} strokeWidth={2.2} />
                  </div>
                  <span style={{ fontFamily: mono, fontSize: 30, color: alpha(c.foreground, 0.4), fontWeight: 600 }}>{tile.n}</span>
                </div>
                {i === 0 && <FindDemo t={demo} />}
                {i === 1 && <NameDemo t={demo} start={d + 30} />}
                {i === 2 && <LinkDemo t={demo} start={d + 30} />}
                <div style={{ ...display, fontSize: 84, fontWeight: 700 }}>{tile.label}</div>
                <Shine at={d + 18} duration={36} />
              </div>
            );
          })}
        </AbsoluteFill>
        <AbsoluteFill style={{ top: 815, height: 120, alignItems: "center" }}>
          <div style={{ display: "flex", gap: 34, alignItems: "center", fontFamily: mono, fontSize: 44, fontWeight: 500, color: c.foreground, opacity: under, transform: `translateY(${(1 - under) * 30}px)` }}>
            {segs.map((t, i) => {
              const s = useSpring(150 + i * 14, { damping: 14 });
              const last = i === segs.length - 1;
              return (
                <div key={t} style={{ display: "flex", alignItems: "center", gap: 34 }}>
                  {i > 0 && <span style={{ color: c.primary, opacity: s }}>·</span>}
                  <span style={{ position: "relative", display: "inline-block", opacity: s, transform: `scale(${0.7 + 0.3 * s})`, color: last ? c.review : c.foreground, fontWeight: last ? 700 : 500 }}>
                    {t}
                    {last && (
                      <svg width={300} height={26} viewBox="0 0 304 26" style={{ position: "absolute", left: -4, top: "100%", width: "110%" }}>
                        <path d={ulPath} fill="none" stroke={c.review} strokeWidth={5} strokeLinecap="round" strokeDasharray={ulEvo.strokeDasharray} strokeDashoffset={ulEvo.strokeDashoffset} />
                      </svg>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        </AbsoluteFill>
      </Backdrop>
    </Exit>
  );
}
