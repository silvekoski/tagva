import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Backdrop, Chars, clamp, display, easeInOut, easeOut, Logo, Shine, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

export function M17Close() {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const logo = useSpring(6, { damping: 12, stiffness: 70 });
  const wipe = interpolate(frame, [6, 40], [0, 105], { ...clamp, easing: easeOut });
  const rule = interpolate(frame, [36, 70], [0, 1], { ...clamp, easing: easeInOut });
  const fade = interpolate(frame, [durationInFrames - 40, durationInFrames - 1], [1, 0], { ...clamp, easing: easeInOut });
  const veo = useSpring(80, { damping: 16 });
  const ring = (frame % 90) / 90;

  return (
    <AbsoluteFill style={{ opacity: fade, background: c.void }}>
      <Backdrop glow={1.2}>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          {[0, 0.33, 0.66].map((o) => {
            const r = (ring + o) % 1;
            return <div key={o} style={{ position: "absolute", width: 500 + r * 1300, height: 500 + r * 1300, borderRadius: "50%", border: `2px solid ${alpha(c.primary, 0.5)}`, opacity: (1 - r) * 0.5 * logo }} />;
          })}
        </AbsoluteFill>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 44, top: -40 }}>
          <div style={{ filter: `drop-shadow(0 0 70px ${alpha(c.primary, 0.6)})`, transform: `scale(${0.85 + 0.15 * logo})` }}>
            <div style={{ position: "relative", clipPath: `inset(-20% ${100 - wipe}% -20% 0)` }}>
              <Logo name="tagva" height={280} fill={`linear-gradient(100deg, ${c.foreground} 10%, ${c.primary} 60%, ${c.veo})`} />
              <Shine at={48} duration={36} strength={0.9} />
              <Shine at={190} duration={36} strength={0.6} />
            </div>
          </div>
          <div style={{ width: 760 * rule, height: 2, background: `linear-gradient(90deg, transparent, ${c.primary}, ${c.veo}, transparent)` }} />
          <div style={{ fontFamily: mono, fontSize: 44, fontWeight: 600, color: c.foreground, display: "flex", gap: 28 }}>
            <Chars text="tagva.bobs.build" delay={52} stagger={1.2} from={24} />
            <span style={{ color: c.primary, opacity: interpolate(frame, [70, 80], [0, 1], clamp) }}>·</span>
            <Chars text="yard.bobs.build" delay={72} stagger={1.2} from={24} />
          </div>
          <div style={{ ...display, fontSize: 36, fontWeight: 500, color: c.muted, letterSpacing: "0.02em" }}>
            <Chars text="team bob the builder" delay={92} stagger={1.2} from={18} blur={8} />
          </div>
        </AbsoluteFill>
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 70 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 18, opacity: veo * 0.9, transform: `translateY(${(1 - veo) * 20}px)` }}>
            <Logo name="veo" height={30} fill={c.veo} />
            <span style={{ fontFamily: mono, fontSize: 22, color: c.muted, letterSpacing: "0.16em" }}>HACKATHON CHALLENGE</span>
          </div>
        </AbsoluteFill>
      </Backdrop>
    </AbsoluteFill>
  );
}
