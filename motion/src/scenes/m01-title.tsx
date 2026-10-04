import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import data from "../data.json";
import { Backdrop, Brackets, Chars, clamp, display, easeInOut, easeOut, Exit, Logo, Shine, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const crop = { x: 5300, y: 1250, scale: 1920 / 2400 };
const markers = data.sweep02.map((b) => ({
  ...b,
  cx: (b.x + b.w / 2 - crop.x) * crop.scale,
  cy: (b.y + b.h / 2 - crop.y) * crop.scale,
}));
const order = [5, 0, 1, 2, 3, 4];
const reveal = 118;
const focus = markers[4];

function Marker({ m, delay, below }: { m: (typeof markers)[number]; delay: number; below: boolean }) {
  const frame = useCurrentFrame();
  const s = useSpring(delay, { damping: 11, stiffness: 160 });
  const ping = ((frame - delay) % 34) / 34;
  const size = Math.max(54, m.w * crop.scale * 1.7);
  const label = m.cab.split(" ")[0];
  if (frame < delay) return null;
  return (
    <div style={{ position: "absolute", left: m.cx, top: m.cy, transform: "translate(-50%, -50%)" }}>
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          width: size * (1 + ping * 1.6),
          height: size * (1 + ping * 1.6),
          transform: "translate(-50%, -50%)",
          borderRadius: "50%",
          border: `3px solid ${c.ok}`,
          opacity: (1 - ping) * 0.8,
        }}
      />
      <div style={{ position: "relative", width: size, height: size, transform: `scale(${2.4 - 1.4 * s})`, opacity: Math.min(1, s * 2) }}>
        <Brackets w={size} h={size} color={c.ok} thickness={4} progress={s} />
        <div style={{ position: "absolute", left: "50%", top: "50%", width: 10, height: 10, borderRadius: 5, transform: "translate(-50%, -50%)", background: c.ok, boxShadow: `0 0 18px 4px ${c.ok}` }} />
      </div>
      <div
        style={{
          position: "absolute",
          left: "50%",
          ...(below ? { top: size / 2 + 16 } : { bottom: size / 2 + 16 }),
          transform: `translate(-50%, ${(1 - s) * (below ? -16 : 16)}px)`,
          opacity: s,
          fontFamily: mono,
          fontSize: 17,
          fontWeight: 600,
          color: c.foreground,
          whiteSpace: "nowrap",
          padding: "5px 10px",
          borderRadius: 8,
          background: alpha(c.void, 0.82),
          border: `1.5px solid ${c.ok}`,
        }}
      >
        REX615 · {label}
      </div>
    </div>
  );
}

export function M01Title({ overlay = false }: { overlay?: boolean }) {
  const frame = useCurrentFrame();
  const push = interpolate(frame, [0, reveal + 20], [1, 1.12], clamp);
  const iris = interpolate(frame, [reveal - 6, reveal + 26], [0, 140], { ...clamp, easing: easeInOut });
  const flash = interpolate(frame, [reveal - 4, reveal + 2, reveal + 16], [0, 0.9, 0], clamp);
  const logoS = useSpring(reveal + 8, { damping: 13, stiffness: 90 });
  const wipe = interpolate(frame, [reveal + 6, reveal + 34], [0, 105], { ...clamp, easing: easeOut });
  const veoS = useSpring(reveal + 34, { damping: 16 });
  const ox = (focus.cx / 1920) * 100;
  const oy = (focus.cy / 1080) * 100;

  return (
    <AbsoluteFill style={{ background: overlay ? "transparent" : c.void }}>
      <AbsoluteFill style={{ transform: `scale(${push})`, transformOrigin: `${ox}% ${oy}%` }}>
        {!overlay && (
          <>
            <Img src={staticFile("img/pano-crop.jpg")} style={{ width: 1920, height: 1080, objectFit: "cover" }} />
            <AbsoluteFill style={{ background: `linear-gradient(180deg, ${alpha(c.void, 0.55)}, ${alpha(c.void, 0.25)} 40%, ${alpha(c.void, 0.7)})` }} />
          </>
        )}
        {markers.map((m, i) => (
          <Marker key={m.cab} m={m} delay={10 + order.indexOf(i) * 9} below={i === 0 || i === 2} />
        ))}
      </AbsoluteFill>

      <AbsoluteFill style={{ clipPath: `circle(${iris}% at ${ox}% ${oy}%)` }}>
        <Exit duration={16}>
          <Backdrop>
            <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 54 }}>
              <div
                style={{
                  position: "relative",
                  transform: `scale(${0.82 + 0.18 * logoS})`,
                  filter: `blur(${(1 - Math.min(1, logoS)) * 18}px) drop-shadow(0 0 60px ${alpha(c.primary, 0.55)})`,
                }}
              >
                <div style={{ position: "relative", clipPath: `inset(-20% ${100 - wipe}% -20% 0)` }}>
                  <Logo name="tagva" height={250} fill={`linear-gradient(100deg, ${c.foreground} 10%, ${c.primary} 60%, ${c.veo})`} />
                  <Shine at={reveal + 40} duration={34} strength={0.9} />
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 26, opacity: veoS, transform: `translateY(${(1 - veoS) * 30}px)` }}>
                <Logo name="veo" height={44} fill={c.veo} />
                <div style={{ width: 2, height: 44 * veoS, background: alpha(c.foreground, 0.35) }} />
                <span style={{ ...display, fontSize: 44, fontWeight: 500, letterSpacing: "-0.01em" }}>
                  <Chars text="hackathon challenge" delay={reveal + 40} stagger={1.1} from={24} />
                </span>
              </div>
              <div style={{ fontFamily: mono, fontSize: 30, color: c.muted, letterSpacing: "0.12em" }}>
                <Chars text="by bob the builder" delay={reveal + 58} stagger={1.4} from={20} blur={8} />
              </div>
            </AbsoluteFill>
          </Backdrop>
        </Exit>
      </AbsoluteFill>
      <AbsoluteFill style={{ background: c.foreground, opacity: flash * (overlay ? 0 : 1), mixBlendMode: "overlay" }} />
    </AbsoluteFill>
  );
}
