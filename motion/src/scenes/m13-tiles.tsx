import { AbsoluteFill, Img, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import data from "../data.json";
import { Backdrop, Brackets, clamp, Count, display, easeInOut, easeOut, Exit, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const W = 1560;
const H = W / 2;
const cw = W / 6;
const ch = H / 6;
const roll = 1039;
const src = 8192;
const lit = [15, 16, 17];
const boxes = data.sweep03.map((b) => {
  const x = (((b.x - roll) % src) + src) % src;
  return { x: (x / src) * W, y: (b.y / 4096) * H, w: (b.w / src) * W, h: (b.h / 4096) * H };
});
const split = 46;
const light = 104;
const tally = 150;

export function M13Tiles() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const unroll = interpolate(frame, [4, 30], [0, 1], { ...clamp, easing: easeInOut });
  const unrollV = interpolate(frame, [22, 44], [0.06, 1], { ...clamp, easing: easeInOut });
  const open = interpolate(frame, [split, split + 34], [0, 1], { ...clamp, easing: easeOut });
  const shrink = interpolate(frame, [tally, tally + 30], [0, 1], { ...clamp, easing: easeInOut });
  const label = useSpring(10, { damping: 16 });
  const sp = 22;
  const gw = W + sp * 5;
  const gh = H + sp * 5;
  const x0 = (1920 - gw) / 2;
  const y0 = 130;

  return (
    <Exit>
      <Backdrop grid={false}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 50, textAlign: "center", fontFamily: mono, fontSize: 24, letterSpacing: "0.3em", color: c.veo, opacity: label }}>ONE PANORAMA · 8K · SWEEP-03</div>
        <AbsoluteFill style={{ transform: `translateY(${-shrink * 70}px) scale(${1 - shrink * 0.22})`, transformOrigin: "50% 20%", clipPath: `inset(${(1 - unrollV) * 40}% ${(1 - unroll) * 50}%)` }}>
          {Array.from({ length: 36 }, (_, i) => {
            const col = i % 6;
            const row = Math.floor(i / 6);
            const ss = spring({ frame: frame - split - (col + row) * 1.5, fps, config: { damping: 13, stiffness: 110 } });
            const gapX = sp * col * ss;
            const gapY = sp * row * ss;
            const left = (1920 - W) / 2 + col * cw - (sp * 5 * ss) / 2 + gapX;
            const top = y0 + row * ch - (sp * 5 * ss) / 2 + gapY + sp * 2.5;
            const isLit = lit.includes(i);
            const glow = interpolate(frame, [light + lit.indexOf(i) * 8, light + lit.indexOf(i) * 8 + 10], [0, 1], clamp);
            const on = isLit ? glow : 0;
            const dim = frame > light ? (isLit ? 1 : 0.38) : 1;
            const rot = (random(`r${i}`) - 0.5) * 18 * (1 - ss) * open;
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left,
                  top,
                  width: cw,
                  height: ch,
                  overflow: "hidden",
                  borderRadius: 10 * ss,
                  border: ss > 0.05 ? `1.5px solid ${on ? c.ok : alpha(c.border, 0.6)}` : undefined,
                  boxShadow: on ? `0 0 ${40 * on}px ${alpha(c.ok, 0.7)}` : undefined,
                  transform: `rotate(${rot}deg) scale(${1 + on * 0.08})`,
                  zIndex: isLit ? 2 : 1,
                  opacity: dim,
                }}
              >
                <Img src={staticFile("img/pano-03-rolled.jpg")} style={{ position: "absolute", width: W, height: H, left: -col * cw, top: -row * ch, maxWidth: "none" }} />
                {isLit &&
                  boxes
                    .filter((b) => b.x >= col * cw && b.x < (col + 1) * cw && b.y >= row * ch && b.y < (row + 1) * ch)
                    .map((b, j) => {
                      const s = interpolate(frame, [light + lit.indexOf(i) * 8 + j * 3, light + lit.indexOf(i) * 8 + j * 3 + 8], [0, 1], { ...clamp, easing: easeOut });
                      const w = Math.max(14, b.w * 1.6);
                      const h = Math.max(14, b.h * 1.6);
                      return (
                        <div key={j} style={{ position: "absolute", left: b.x - col * cw + b.w / 2 - w / 2, top: b.y - row * ch + b.h / 2 - h / 2, width: w, height: h, transform: `scale(${2.2 - 1.2 * s})`, opacity: s }}>
                          <Brackets w={w} h={h} color={c.ok} progress={s} thickness={2.5} arm={0.4} />
                        </div>
                      );
                    })}
              </div>
            );
          })}
        </AbsoluteFill>
        <AbsoluteFill style={{ top: 880, alignItems: "center", gap: 26 }}>
          <div style={{ ...display, fontSize: 76, fontWeight: 750, display: "flex", gap: 26, alignItems: "baseline", fontVariantNumeric: "tabular-nums", opacity: interpolate(frame, [tally - 10, tally + 6], [0, 1], clamp) }}>
            <span>36 tiles</span>
            <span style={{ color: c.primary }}>×</span>
            <span>
              <Count to={18} start={tally} end={tally + 34} /> positions
            </span>
            <span style={{ color: c.primary }}>=</span>
            <span style={{ color: c.ok, textShadow: `0 0 40px ${alpha(c.ok, 0.6)}` }}>
              <Count to={648} start={tally} end={tally + 34} />
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {Array.from({ length: 18 }, (_, i) => {
              const s = spring({ frame: frame - tally - i * 1.8, fps, config: { damping: 12 } });
              return <div key={i} style={{ width: 54, height: 27, borderRadius: 5, background: `linear-gradient(135deg, ${c.primary}, ${c.veo})`, opacity: s, transform: `scale(${s})`, boxShadow: `0 0 12px ${alpha(c.primary, 0.5)}` }} />;
            })}
          </div>
        </AbsoluteFill>
      </Backdrop>
    </Exit>
  );
}
