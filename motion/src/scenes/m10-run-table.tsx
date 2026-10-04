import { CircleCheck, OctagonX } from "lucide-react";
import { AbsoluteFill, interpolate, random, useCurrentFrame } from "remotion";
import { Backdrop, clamp, Count, display, easeInOut, Exit, Kicker, useSpring } from "../kit";
import { alpha, c, mono } from "../theme";

const runs = [
  { id: "r1-base-s", found: 6, fp: 2, pass: false, note: "base 6,000 · fired on 2 non-relays" },
  { id: "r2-mix-s", found: 6, fp: 0, pass: true, note: "+1,500 dark · +1,500 occluded" },
  { id: "r3-base-m", found: 6, fp: 1, pass: true, note: "base 6,000 · YOLO26m" },
];
const cols = [520, 300, 340, 330];
const rowStart = [30, 120, 210];
const select = 300;
const rowH = 150;

function Row({ r, i }: { r: (typeof runs)[number]; i: number }) {
  const frame = useCurrentFrame();
  const d = rowStart[i];
  const s = useSpring(d, { damping: 15, stiffness: 120 });
  const stamp = useSpring(d + 40, { damping: 9, stiffness: 200 });
  const sel = useSpring(select, { damping: 13 });
  const selected = i === 1;
  const dim = selected ? 1 : 1 - 0.55 * sel;
  const shake = !r.pass && frame > d + 40 && frame < d + 52 ? (random(`s${frame}`) - 0.5) * 16 : 0;
  const verdict = r.pass ? c.ok : c.destructive;
  const typed = Math.min(r.id.length, Math.max(0, Math.floor((frame - d - 4) / 1.5)));
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        height: rowH,
        borderRadius: 22,
        padding: "0 34px",
        marginBottom: 18,
        background: selected ? alpha(c.ok, 0.08 * sel) : alpha(c.card, 0.55),
        border: `2px solid ${selected ? alpha(c.ok, 0.25 + 0.75 * sel) : alpha(c.border, 0.4)}`,
        boxShadow: selected ? `0 0 ${90 * sel}px -10px ${alpha(c.ok, 0.6)}` : undefined,
        transform: `translateX(${(1 - s) * 300 + shake}px) scale(${selected ? 1 + 0.04 * sel : 1 - 0.02 * sel})`,
        opacity: Math.min(1, s * 2) * dim,
      }}
    >
      <div style={{ width: cols[0] }}>
        <div style={{ fontFamily: mono, fontSize: 44, fontWeight: 700, color: c.foreground }}>
          {r.id.slice(0, typed)}
          {typed < r.id.length && <span style={{ color: c.primary }}>▍</span>}
        </div>
        <div style={{ fontFamily: mono, fontSize: 21, color: c.muted, marginTop: 8, opacity: interpolate(frame, [d + 30, d + 44], [0, 1], clamp) }}>{r.note}</div>
      </div>
      <div style={{ width: cols[1], ...display, fontSize: 60, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
        <Count to={r.found} start={d + 10} end={d + 30} /> / 6
      </div>
      <div style={{ width: cols[2], ...display, fontSize: 60, fontWeight: 700, color: r.fp > 1 ? c.destructive : r.fp ? c.review : c.ok, fontVariantNumeric: "tabular-nums" }}>
        <Count to={r.fp} start={d + 18} end={d + 34} />
      </div>
      <div style={{ width: cols[3], display: "flex", alignItems: "center", gap: 16 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "12px 24px",
            borderRadius: 14,
            border: `3px solid ${verdict}`,
            color: verdict,
            fontFamily: mono,
            fontSize: 36,
            fontWeight: 800,
            letterSpacing: "0.12em",
            background: alpha(verdict, 0.12),
            transform: `scale(${interpolate(stamp, [0, 1], [2.6, 1])}) rotate(${(1 - stamp) * -14}deg)`,
            opacity: frame < d + 40 ? 0 : Math.min(1, stamp * 2),
            boxShadow: `0 0 30px ${alpha(verdict, 0.5)}`,
          }}
        >
          {r.pass ? <CircleCheck size={34} strokeWidth={2.6} /> : <OctagonX size={34} strokeWidth={2.6} />}
          {r.pass ? "PASS" : "FAIL"}
        </div>
      </div>
      {selected && (
        <div style={{ position: "absolute", right: -26, top: -26, padding: "10px 22px", borderRadius: 999, background: c.primary, color: c.void, fontFamily: mono, fontSize: 24, fontWeight: 800, letterSpacing: "0.14em", transform: `scale(${sel}) rotate(${(1 - sel) * 20}deg)`, boxShadow: `0 0 40px ${c.primary}` }}>SELECTED</div>
      )}
    </div>
  );
}

export function M10RunTable() {
  const frame = useCurrentFrame();
  const head = useSpring(4, { damping: 18 });
  const line = interpolate(frame, [10, 40], [0, 1], { ...clamp, easing: easeInOut });
  const ship = useSpring(select + 30, { damping: 16 });
  return (
    <Exit>
      <Backdrop grid={false}>
        <AbsoluteFill style={{ padding: "90px 200px", flexDirection: "column" }}>
          <Kicker color={c.primary}>Training runs</Kicker>
          <div style={{ display: "flex", padding: "50px 34px 18px", opacity: head, fontFamily: mono, fontSize: 24, letterSpacing: "0.2em", color: c.muted, textTransform: "uppercase" }}>
            {["Run", "Relays found", "False positives", "Result"].map((h, i) => (
              <div key={h} style={{ width: cols[i] }}>{h}</div>
            ))}
          </div>
          <div style={{ height: 2, width: `${line * 100}%`, background: `linear-gradient(90deg, ${c.primary}, ${c.veo}, transparent)`, marginBottom: 26 }} />
          {runs.map((r, i) => (
            <Row key={r.id} r={r} i={i} />
          ))}
          <div style={{ marginTop: 26, fontFamily: mono, fontSize: 30, color: c.foreground, opacity: ship, transform: `translateY(${(1 - ship) * 20}px)` }}>
            <span style={{ color: c.primary }}>r2-mix-s</span> runs in Tagva today · 6 / 6 · 0 false positives
          </div>
        </AbsoluteFill>
      </Backdrop>
    </Exit>
  );
}
