import { AbsoluteFill, Img, staticFile } from "remotion";
import data from "../data.json";
import { Backdrop, Brackets, brandText, display, glass, Logo } from "../kit";
import { alpha, c, mono } from "../theme";

const view = { width: 1000, height: 540, scale: 0.75, left: -340, top: -150 };
const crop = { x: 5300, y: 1250, scale: 1920 / 2400 };
const markers = data.sweep02
  .map((b) => ({
    ...b,
    cx: (b.x + b.w / 2 - crop.x) * crop.scale * view.scale + view.left,
    cy: (b.y + b.h / 2 - crop.y) * crop.scale * view.scale + view.top,
    size: Math.max(34, b.w * crop.scale * view.scale * 1.7),
  }))
  .sort((a, b) => a.cx - b.cx);

export function ReadmeHeader() {
  return (
    <Backdrop>
      <AbsoluteFill style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: "0 64px 0 110px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 34 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <Logo name="veo" height={26} fill={c.veo} />
            <span style={{ fontFamily: mono, fontSize: 20, fontWeight: 600, color: c.muted, letterSpacing: "0.22em" }}>HACKATHON CHALLENGE</span>
          </div>
          <div style={{ filter: `drop-shadow(0 0 50px ${alpha(c.primary, 0.55)})` }}>
            <Logo name="tagva" height={150} fill={`linear-gradient(100deg, ${c.foreground} 10%, ${c.primary} 60%, ${c.veo})`} />
          </div>
          <div style={{ ...display, ...brandText, fontSize: 44, fontWeight: 600, lineHeight: 1.15, maxWidth: 640 }}>Find each REX615 relay in a Matterport scan</div>
          <div style={{ width: 520, height: 2, background: `linear-gradient(90deg, ${c.primary}, ${c.veo}, transparent)` }} />
          <div style={{ fontFamily: mono, fontSize: 20, color: c.muted, letterSpacing: "0.08em" }}>YOLO26 · PP-OCRv5 · BLENDER · THREE.JS</div>
        </div>
        <div style={{ ...glass(c.ok), position: "relative", width: view.width, height: view.height, overflow: "hidden", borderRadius: 24 }}>
          <Img
            src={staticFile("img/pano-crop.jpg")}
            style={{ position: "absolute", left: view.left, top: view.top, width: 1920 * view.scale, height: 1080 * view.scale }}
          />
          <AbsoluteFill style={{ background: `linear-gradient(180deg, ${alpha(c.void, 0.45)}, ${alpha(c.void, 0.1)} 45%, ${alpha(c.void, 0.55)})` }} />
          {markers.map((m, i) => (
            <div key={m.cab} style={{ position: "absolute", left: m.cx, top: m.cy, transform: "translate(-50%, -50%)" }}>
              <div style={{ position: "relative", width: m.size, height: m.size }}>
                <Brackets w={m.size} h={m.size} color={c.ok} thickness={3} />
                <div style={{ position: "absolute", left: "50%", top: "50%", width: 8, height: 8, borderRadius: 4, transform: "translate(-50%, -50%)", background: c.ok, boxShadow: `0 0 14px 3px ${c.ok}` }} />
              </div>
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  ...(i % 2 ? { top: m.size / 2 + 12 } : { bottom: m.size / 2 + 12 }),
                  transform: "translateX(-50%)",
                  fontFamily: mono,
                  fontSize: 15,
                  fontWeight: 600,
                  color: c.foreground,
                  whiteSpace: "nowrap",
                  padding: "4px 8px",
                  borderRadius: 7,
                  background: alpha(c.void, 0.82),
                  border: `1.5px solid ${c.ok}`,
                }}
              >
                {m.cab.split(" ")[0]} · {m.c.toFixed(2)}
              </div>
            </div>
          ))}
          <div
            style={{
              position: "absolute",
              left: 24,
              bottom: 22,
              fontFamily: mono,
              fontSize: 16,
              fontWeight: 600,
              letterSpacing: "0.16em",
              color: c.ok,
              padding: "6px 12px",
              borderRadius: 8,
              background: alpha(c.void, 0.75),
            }}
          >
            6 REX615 · SWEEP-02
          </div>
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
}
