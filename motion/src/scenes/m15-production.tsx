import { MapPin } from "lucide-react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Backdrop, clamp, display, easeInOut, Exit, glass, Logo, Shine, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const cardW = 440;
const gap = 140;
const x0 = (1920 - 3 * cardW - 2 * gap) / 2;
const y = 380;
const cardH = 300;

export function M15Production() {
  const frame = useCurrentFrame();
  const cards = [
    { body: <Logo name="tagva" height={86} />, sub: "tags + documents", color: c.primary },
    { body: <Img src={staticFile("logos/matterport-logo.svg")} style={{ height: 62 }} />, sub: "API", color: c.destructive },
    { body: <div style={{ display: "flex", alignItems: "center", gap: 14 }}><Logo name="veo" height={58} fill={c.veo} /><span style={{ ...display, fontSize: 68, fontWeight: 700, color: c.veo }}>360</span></div>, sub: "viewer customers use", color: c.veo },
  ];
  return (
    <Exit duration={10}>
      <Backdrop>
        <AbsoluteFill style={{ alignItems: "center", top: 170 }}>
          <div style={{ fontFamily: mono, fontSize: 26, letterSpacing: "0.3em", color: c.muted, opacity: interpolate(frame, [0, 12], [0, 1], clamp) }}>IN PRODUCTION</div>
        </AbsoluteFill>
        {cards.slice(0, -1).map((cd, i) => {
          const draw = interpolate(frame, [14 + i * 16, 30 + i * 16], [0, 1], { ...clamp, easing: easeInOut });
          const left = x0 + (i + 1) * cardW + i * gap;
          return (
            <div key={i} style={{ position: "absolute", left: left + 8, top: y + cardH / 2 - 2, width: (gap - 16) * draw, height: 4, background: `linear-gradient(90deg, ${cd.color}, ${cards[i + 1].color})`, boxShadow: `0 0 18px ${cd.color}` }}>
              {draw >= 1 &&
                [0, 0.5].map((o) => {
                  const p = ((frame - 30 - i * 16) / 30 + o) % 1;
                  return (
                    <div key={o} style={{ position: "absolute", left: p * (gap - 16) - 18, top: -40, opacity: Math.sin(p * Math.PI) }}>
                      <MapPin size={36} color={c.ok} fill={alpha(c.ok, 0.3)} strokeWidth={2.4} />
                    </div>
                  );
                })}
            </div>
          );
        })}
        {cards.map((cd, i) => {
          const s = useSpring(i * 12, { damping: 12, stiffness: 130 });
          return (
            <div key={i} style={{ position: "absolute", left: x0 + i * (cardW + gap), top: y, width: cardW, height: cardH, ...glass(cd.color), display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 28, transform: `translateY(${(1 - s) * 120}px) scale(${0.8 + 0.2 * s})`, opacity: Math.min(1, s * 2), overflow: "hidden" }}>
              {cd.body}
              <div style={{ fontFamily: mono, fontSize: 26, color: c.muted }}>{cd.sub}</div>
              <Shine at={i * 12 + 10} duration={26} />
            </div>
          );
        })}
      </Backdrop>
    </Exit>
  );
}
