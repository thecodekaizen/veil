import { Video } from "@remotion/media";
import { AbsoluteFill, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EASE, clamp } from "../theme";

const SRC_W = 2560;
const SRC_H = 1440;

/** A camera key: from local frame `at`, frame the source-pixel box [x, y, w, h] (null = full view). */
export type ZoomKey = { at: number; box: [number, number, number, number] | null; pad?: number };
export type CursorKey = { at: number; x: number; y: number; click?: boolean };

type View = { cx: number; cy: number; s: number };
const full: View = { cx: SRC_W / 2, cy: SRC_H / 2, s: 1 };

const viewFor = (k: ZoomKey): View => {
  if (!k.box) return full;
  const [x, y, w, h] = k.box;
  const pad = k.pad ?? 1.12;
  const s = Math.min(2.2, Math.max(1, Math.min(SRC_W / (w * pad), SRC_H / (h * pad))));
  // keep the frame inside the source
  const hw = SRC_W / (2 * s), hh = SRC_H / (2 * s);
  return { cx: Math.min(SRC_W - hw, Math.max(hw, x + w / 2)), cy: Math.min(SRC_H - hh, Math.max(hh, y + h / 2)), s };
};

/**
 * Real product footage (Playwright capture of the Veil UI) in a floating rounded window,
 * with spring-eased auto-zoom between camera keys and an optional re-rendered cursor.
 */
export const Window: React.FC<{
  src: string;
  trimBeforeSec?: number;
  rate?: number;
  zoom?: ZoomKey[];
  cursor?: CursorKey[];
  width?: number;
  top?: number;
}> = ({ src, trimBeforeSec = 0, rate = 1, zoom = [], cursor = [], width = 1640, top = 84 }) => {
  const frame = useCurrentFrame();
  const { fps, width: compW } = useVideoConfig();
  const height = (width * SRC_H) / SRC_W;
  const base = width / SRC_W;

  // camera
  const keys = zoom.length ? zoom : [{ at: 0, box: null }];
  let prev: View = full;
  let cur: View = viewFor(keys[0]);
  let since = keys[0].at;
  for (let i = 0; i < keys.length; i++) {
    if (frame >= keys[i].at) {
      prev = i === 0 ? full : viewFor(keys[i - 1]);
      cur = viewFor(keys[i]);
      since = keys[i].at;
    }
  }
  const t = interpolate(frame, [since, since + 22], [0, 1], { ...clamp, easing: EASE });
  const v = { cx: prev.cx + (cur.cx - prev.cx) * t, cy: prev.cy + (cur.cy - prev.cy) * t, s: prev.s * Math.pow(cur.s / prev.s, t) };
  const scale = base * v.s;
  const tx = width / 2 - v.cx * scale;
  const ty = height / 2 - v.cy * scale;

  // cursor (source px -> window px through the same camera)
  let cx = -100, cy = -100, ripple = 0;
  const ck = cursor.filter((c) => frame >= c.at);
  if (cursor.length && ck.length) {
    const i = ck.length - 1;
    const a = cursor[i], b = cursor[i + 1];
    const p = b ? interpolate(frame, [b.at - 18, b.at], [0, 1], { ...clamp, easing: EASE }) : 0;
    const sx = b ? a.x + (b.x - a.x) * p : a.x;
    const sy = b ? a.y + (b.y - a.y) * p : a.y;
    cx = tx + sx * scale;
    cy = ty + sy * scale;
    const lastClick = [...ck].reverse().find((c) => c.click);
    if (lastClick) ripple = interpolate(frame, [lastClick.at, lastClick.at + 14], [0, 1], clamp);
  }

  const enter = interpolate(frame, [0, 14], [0, 1], { ...clamp, easing: EASE });
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: (compW - width) / 2,
          top,
          width,
          height,
          borderRadius: 20,
          overflow: "hidden",
          background: C.panel,
          border: `1px solid ${C.line}`,
          boxShadow: "0 40px 120px rgba(0,0,0,0.55), 0 8px 24px rgba(0,0,0,0.4)",
          opacity: enter,
          translate: `0px ${interpolate(enter, [0, 1], [24, 0])}px`,
        }}
      >
        <div style={{ position: "absolute", left: 0, top: 0, width: SRC_W, height: SRC_H, transformOrigin: "0 0", transform: `translate(${tx}px, ${ty}px) scale(${scale})` }}>
          <Video src={staticFile(src)} trimBefore={Math.round(trimBeforeSec * fps)} playbackRate={rate} muted style={{ width: SRC_W, height: SRC_H }} />
        </div>
        {cursor.length > 0 && (
          <>
            <div style={{ position: "absolute", left: cx - 22, top: cy - 22, width: 44, height: 44, borderRadius: 22, border: `3px solid ${C.amber}`, opacity: ripple > 0 && ripple < 1 ? 1 - ripple : 0, scale: `${0.4 + ripple * 1.4}` }} />
            <svg style={{ position: "absolute", left: cx - 4, top: cy - 3 }} width="30" height="38" viewBox="0 0 30 38">
              <path d="M3 2 L3 30 L10 23 L15 35 L20 33 L15 21 L25 21 Z" fill="#fff" stroke="#111" strokeWidth="2" strokeLinejoin="round" />
            </svg>
          </>
        )}
      </div>
    </AbsoluteFill>
  );
};
