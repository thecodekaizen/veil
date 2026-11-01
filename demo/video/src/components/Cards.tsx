import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { C, EASE, body, clamp, display, mono } from "../theme";

const rise = (frame: number, from: number, dist = 30) => ({
  opacity: interpolate(frame, [from, from + 10], [0, 1], clamp),
  translate: `0px ${interpolate(frame, [from, from + 14], [dist, 0], { ...clamp, easing: EASE })}px`,
});

/** Word-by-word kinetic title. `words[i].at` is the local frame each word lands (from the VO timing map). */
export const KineticTitle: React.FC<{ words: { text: string; at: number; accent?: boolean }[]; size?: number; top?: number }> = ({
  words, size = 150, top,
}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: top === undefined ? "center" : "flex-start", alignItems: "center", paddingTop: top }}>
      <div style={{ display: "flex", gap: size * 0.32, flexWrap: "wrap", justifyContent: "center", maxWidth: 1700 }}>
        {words.map((w, i) => (
          <span
            key={i}
            style={{
              fontFamily: display,
              fontWeight: 700,
              fontSize: size,
              letterSpacing: "-0.02em",
              color: w.accent ? C.amber : C.text,
              textShadow: "0 6px 40px rgba(0,0,0,0.6)",
              display: "inline-block",
              clipPath: `inset(0 0 ${interpolate(frame, [w.at, w.at + 9], [100, 0], { ...clamp, easing: EASE })}% 0)`,
              ...rise(frame, w.at, size * 0.3),
            }}
          >
            {w.text}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/** Big number card: "0 / 4" with a label, optional strike-through and a second value. */
export const StatCard: React.FC<{
  value: string; label: string; at?: number; next?: { value: string; label: string; at: number }; note?: { text: string; at: number };
}> = ({ value, label, at = 0, next, note }) => {
  const frame = useCurrentFrame();
  const swap = next ? interpolate(frame, [next.at, next.at + 12], [0, 1], { ...clamp, easing: EASE }) : 0;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 28 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 90 }}>
        <div style={{ textAlign: "center", ...rise(frame, at), opacity: interpolate(frame, [at, at + 10], [0, 1], clamp) * (1 - swap * 0.6) }}>
          <div style={{ fontFamily: display, fontWeight: 700, fontSize: 260, lineHeight: 1, color: next ? C.dim : C.red }}>{value}</div>
          <div style={{ fontFamily: body, fontSize: 44, color: C.dim, marginTop: 16 }}>{label}</div>
        </div>
        {next && (
          <>
            <div style={{ fontFamily: body, fontSize: 90, color: C.dim, opacity: swap }}>→</div>
            <div style={{ textAlign: "center", ...rise(frame, next.at) }}>
              <div style={{ fontFamily: display, fontWeight: 700, fontSize: 260, lineHeight: 1, color: C.amber }}>{next.value}</div>
              <div style={{ fontFamily: body, fontSize: 44, color: C.text, marginTop: 16 }}>{next.label}</div>
            </div>
          </>
        )}
      </div>
      {note && <div style={{ fontFamily: mono, fontSize: 34, color: C.dim, ...rise(frame, note.at, 16) }}>{note.text}</div>}
    </AbsoluteFill>
  );
};

/** A labelled pill pointing at something on screen (positions in composition px). */
export const Callout: React.FC<{ x: number; y: number; text: string; sub?: string; at: number; color?: string; align?: "left" | "right" }> = ({
  x, y, text, sub, at, color = C.amber, align = "left",
}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute",
        left: align === "left" ? x : undefined,
        right: align === "right" ? 1920 - x : undefined,
        top: y,
        maxWidth: 620,
        padding: "16px 22px",
        borderRadius: 14,
        background: "rgba(20,23,28,0.94)",
        border: `2px solid ${color}`,
        boxShadow: "0 18px 50px rgba(0,0,0,0.5)",
        ...rise(frame, at, 18),
      }}
    >
      <div style={{ fontFamily: body, fontWeight: 700, fontSize: 36, color }}>{text}</div>
      {sub && <div style={{ fontFamily: body, fontSize: 28, color: C.text, marginTop: 6, lineHeight: 1.3 }}>{sub}</div>}
    </div>
  );
};

/** Chip, e.g. "fictional data · composited clip". */
export const Chip: React.FC<{ text: string; at: number; x: number; y: number; color?: string }> = ({ text, at, x, y, color = C.dim }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: x, top: y, padding: "10px 20px", borderRadius: 999, background: "rgba(11,13,16,0.8)", border: `1px solid ${color}`, color, fontFamily: mono, fontSize: 28, ...rise(frame, at, 10) }}>
      {text}
    </div>
  );
};

/** Gate result table, typeset from gate/GATE_RESULT.md and gate/postgate/GATE_RESULT.md. */
export const GateCard: React.FC<{ rows: { g: string; frozen: string; post: string }[]; at: number; postAt: number }> = ({ rows, at, postAt }) => {
  const frame = useCurrentFrame();
  const col = (s: string) => (s.startsWith("PASS") ? C.green : s.startsWith("FAIL") ? C.red : C.dim);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ width: 1500, ...rise(frame, at) }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 380px 520px", fontFamily: mono, fontSize: 34, color: C.dim, padding: "0 0 14px", borderBottom: `1px solid ${C.line}` }}>
          <span>pre-registered gate</span>
          <span>frozen run</span>
          <span style={{ opacity: interpolate(frame, [postAt, postAt + 10], [0, 1], clamp) }}>post-gate fixes (labelled)</span>
        </div>
        {rows.map((r, i) => (
          <div key={r.g} style={{ display: "grid", gridTemplateColumns: "1fr 380px 520px", fontFamily: mono, fontSize: 40, padding: "16px 0", borderBottom: `1px solid ${C.line}`, ...rise(frame, at + 4 + i * 3, 12) }}>
            <span style={{ color: C.text }}>{r.g}</span>
            <span style={{ color: col(r.frozen), fontWeight: 600 }}>{r.frozen}</span>
            <span style={{ color: col(r.post), fontWeight: 600, opacity: interpolate(frame, [postAt + i * 3, postAt + 10 + i * 3], [0, 1], clamp) }}>{r.post}</span>
          </div>
        ))}
        <div style={{ fontFamily: display, fontWeight: 700, fontSize: 64, color: C.red, marginTop: 34, ...rise(frame, postAt + 20) }}>Verdict: FAIL</div>
      </div>
    </AbsoluteFill>
  );
};

/** Terminal showing a real command and lines of its real output (from a live run log). */
export const Terminal: React.FC<{ cmd: string; lines: { text: string; color?: string }[]; at: number }> = ({ cmd, lines, at }) => {
  const frame = useCurrentFrame();
  const typed = Math.floor(interpolate(frame, [at + 6, at + 6 + cmd.length * 0.45], [0, cmd.length], clamp));
  const outAt = at + 10 + cmd.length * 0.45;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ width: 1760, borderRadius: 20, background: "#0E1014", border: `1px solid ${C.line}`, boxShadow: "0 40px 120px rgba(0,0,0,0.55)", overflow: "hidden", ...rise(frame, at) }}>
        <div style={{ display: "flex", gap: 10, padding: "16px 20px", borderBottom: `1px solid ${C.line}` }}>
          {["#E66B5B", "#E8B04A", "#6FCF8F"].map((c) => <div key={c} style={{ width: 16, height: 16, borderRadius: 8, background: c, opacity: 0.8 }} />)}
        </div>
        <div style={{ padding: "26px 34px", fontFamily: mono, fontSize: 28, lineHeight: 1.6, color: C.text, whiteSpace: "pre" }}>
          <div><span style={{ color: C.green }}>$ </span>{cmd.slice(0, typed)}<span style={{ opacity: frame % 30 < 15 ? 1 : 0 }}>▍</span></div>
          {lines.map((l, i) => (
            <div key={i} style={{ color: l.color ?? C.dim, opacity: interpolate(frame, [outAt + i * 4, outAt + i * 4 + 4], [0, 1], clamp) }}>{l.text}</div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
