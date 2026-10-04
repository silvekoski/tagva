import { CameraOff } from "lucide-react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop, clamp, display, easeOut, Exit, useSpring, Words } from "../kit";
import { alpha, c } from "../theme";

export function M05NoPhotos() {
  const frame = useCurrentFrame();
  const icon = useSpring(0, { damping: 10, stiffness: 180 });
  const glow = interpolate(frame, [10, 22, 60], [0, 1, 0.5], { ...clamp, easing: easeOut });
  return (
    <Exit duration={8}>
      <Backdrop glow={1.2}>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 50 }}>
          <div style={{ width: 150, height: 150, borderRadius: 40, display: "grid", placeItems: "center", background: alpha(c.destructive, 0.14), border: `3px solid ${c.destructive}`, transform: `scale(${icon}) rotate(${(1 - icon) * -30}deg)`, boxShadow: `0 0 70px ${alpha(c.destructive, 0.5)}` }}>
            <CameraOff size={84} color={c.destructive} strokeWidth={2.2} />
          </div>
          <Words
            text="No real photos were used in training."
            delay={3}
            stagger={2.2}
            style={{ ...display, fontSize: 92, fontWeight: 750, maxWidth: 1840 }}
            wordStyle={(i) => (i === 0 ? { color: c.destructive, textShadow: `0 0 ${glow * 40}px ${c.destructive}` } : i < 3 ? { color: c.foreground } : { color: alpha(c.foreground, 0.75), fontWeight: 500 })}
          />
        </AbsoluteFill>
      </Backdrop>
    </Exit>
  );
}
