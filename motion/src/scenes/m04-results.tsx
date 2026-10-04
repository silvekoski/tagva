import { CircleCheck, Crosshair, Laptop } from "lucide-react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, Count, easeInOut, easeOut, Logo, Shine, useSpring } from "../kit";
import { alpha, c, mono, sans } from "../theme";

const stats = [
  { Icon: CircleCheck, value: (f: number) => <><Count to={6} start={f} end={f + 22} /> / 6</>, label: "relays found", color: c.ok },
  { Icon: Crosshair, value: () => <>0</>, label: "false positives", color: c.ok },
  { Icon: Laptop, value: () => <>~4 min</>, label: "on a MacBook", color: c.veo },
];

export function M04Results({ overlay = true }: { overlay?: boolean }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const bar = interpolate(frame, [0, 18], [0, 1], { ...clamp, easing: easeOut });
  const out = interpolate(frame, [durationInFrames - 16, durationInFrames - 2], [0, 1], { ...clamp, easing: easeInOut });
  const width = 1500;

  return (
    <AbsoluteFill>
      {!overlay && <Img src={staticFile("img/pano-crop.jpg")} style={{ width: 1920, height: 1080 }} />}
      <div style={{ position: "absolute", left: 90, bottom: 80, width, height: 170, transform: `translateX(${out * -1700}px)` }}>
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 10, borderRadius: 5, background: `linear-gradient(${c.primary}, ${c.veo})`, boxShadow: `0 0 26px ${c.primary}`, transform: `scaleY(${bar})` }} />
        <div
          style={{
            position: "absolute",
            left: 24,
            top: 0,
            bottom: 0,
            width: (width - 24) * bar,
            overflow: "hidden",
            borderRadius: 24,
            background: `linear-gradient(100deg, ${alpha(c.deep, 0.92)}, ${alpha(c.background, 0.86)})`,
            border: `1.5px solid ${alpha(c.primary, 0.5)}`,
            boxShadow: `0 30px 60px -20px ${alpha(c.void, 0.8)}`,
            display: "flex",
            alignItems: "center",
            padding: "0 44px",
            gap: 44,
          }}
        >
          <div style={{ opacity: interpolate(frame, [10, 24], [0, 1], clamp), flexShrink: 0 }}>
            <Logo name="tagva" height={56} />
            <div style={{ fontFamily: mono, fontSize: 17, color: c.muted, marginTop: 8, letterSpacing: "0.16em" }}>VEO-DEMO · RESULT</div>
          </div>
          {stats.map((st, i) => {
            const d = 18 + i * 9;
            const s = useSpring(d, { damping: 13, stiffness: 150 });
            return (
              <div key={st.label} style={{ display: "flex", alignItems: "center", gap: 22, opacity: s, transform: `translateY(${(1 - s) * 50}px)`, flexShrink: 0 }}>
                <div style={{ width: 2, height: 90, background: alpha(c.border, 0.6) }} />
                <div style={{ width: 70, height: 70, borderRadius: 35, display: "grid", placeItems: "center", background: alpha(st.color, 0.16), border: `2.5px solid ${st.color}`, transform: `scale(${s})`, boxShadow: `0 0 26px ${alpha(st.color, 0.5)}` }}>
                  <st.Icon size={38} color={st.color} strokeWidth={2.6} />
                </div>
                <div>
                  <div style={{ fontFamily: sans, fontSize: 60, fontWeight: 750, color: c.foreground, letterSpacing: "-0.03em", lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{st.value(d)}</div>
                  <div style={{ fontFamily: mono, fontSize: 21, color: c.muted, marginTop: 6 }}>{st.label}</div>
                </div>
              </div>
            );
          })}
          <Shine at={52} duration={40} strength={0.35} />
        </div>
      </div>
    </AbsoluteFill>
  );
}
