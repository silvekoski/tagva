import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import data from "../data.json";
import { Brackets, clamp, Count, display, easeOut, Exit, glass, ScanSweep, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const tile = 900;
const tx = 110;
const ty = 90;
const snap = 26;

export function M12DarkRecall({ overlay = false }: { overlay?: boolean }) {
  const frame = useCurrentFrame();
  const enter = useSpring(0, { damping: 16 });
  const panel = useSpring(snap + 18, { damping: 14 });
  const push = interpolate(frame, [0, 180], [1, 1.05], clamp);
  return (
    <Exit duration={12}>
      <AbsoluteFill style={{ background: overlay ? "transparent" : c.void }}>
        {!overlay && (
          <div style={{ position: "absolute", left: tx, top: ty, width: tile, height: tile, borderRadius: 26, overflow: "hidden", border: `2px solid ${alpha(c.border, 0.6)}`, boxShadow: `0 40px 120px -20px ${alpha(c.chart3, 0.5)}`, opacity: enter, transform: `scale(${(0.94 + 0.06 * enter) * push})` }}>
            <Img src={staticFile("img/real-tile-dark.jpg")} style={{ width: "100%", height: "100%" }} />
            <ScanSweep at={8} duration={snap - 4} color={c.ok} />
            {data.realTile.map((b, i) => {
              const s = useSpring(snap + i * 3, { damping: 10, stiffness: 220 });
              const w = Math.max(30, b[2] * tile);
              const h = Math.max(30, b[3] * tile);
              return (
                <div key={i} style={{ position: "absolute", left: b[0] * tile - w / 2, top: b[1] * tile - h / 2, width: w, height: h, transform: `scale(${3 - 2 * s})`, opacity: frame < snap + i * 3 ? 0 : 1 }}>
                  <Brackets w={w} h={h} color={c.ok} progress={s} thickness={3} arm={0.35} />
                </div>
              );
            })}
            <div style={{ position: "absolute", left: 22, top: 22, fontFamily: mono, fontSize: 22, padding: "8px 14px", borderRadius: 10, background: alpha(c.void, 0.8), color: c.muted, border: `1.5px solid ${alpha(c.border, 0.7)}` }}>real tile · darkened</div>
          </div>
        )}
        <div style={{ position: "absolute", right: 110, top: 300, width: 740, padding: "56px 60px", ...glass(c.ok), transform: `translateX(${(1 - panel) * 300}px)`, opacity: panel }}>
          <div style={{ ...display, fontSize: 180, fontWeight: 800, fontVariantNumeric: "tabular-nums", textShadow: `0 0 60px ${alpha(c.ok, 0.5)}` }}>
            <Count to={98.4} start={snap + 18} end={snap + 60} decimals={1} ease={easeOut} />
            <span style={{ fontSize: 100, color: c.ok, marginLeft: 12 }}>%</span>
          </div>
          <div style={{ ...display, fontSize: 52, fontWeight: 600, marginTop: 10 }}>recall in the dark</div>
          <div style={{ height: 2, background: alpha(c.border, 0.6), margin: "36px 0" }} />
          <div style={{ display: "flex", alignItems: "center", gap: 20, opacity: interpolate(frame, [snap + 50, snap + 66], [0, 1], clamp) }}>
            <span style={{ ...display, fontSize: 72, fontWeight: 800, color: c.ok }}>0</span>
            <span style={{ fontFamily: mono, fontSize: 32, color: c.foreground }}>false positives</span>
          </div>
        </div>
      </AbsoluteFill>
    </Exit>
  );
}
