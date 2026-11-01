import { createTikTokStyleCaptions, type Caption, type TikTokPage } from "@remotion/captions";
import { useMemo } from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, T, body, clamp } from "../theme";

const SWITCH_MS = 1500;

const Page: React.FC<{ page: TikTokPage; emphasis: Set<string> }> = ({ page, emphasis }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const now = page.startMs + (frame / fps) * 1000;
  const enter = interpolate(frame, [0, 5], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 54 }}>
      <div
        style={{
          maxWidth: 1400,
          textAlign: "center",
          fontFamily: body,
          fontWeight: 600,
          fontSize: 46,
          lineHeight: 1.25,
          color: C.text,
          whiteSpace: "pre-wrap",
          padding: "10px 26px",
          borderRadius: 14,
          background: "rgba(11,13,16,0.72)",
          opacity: enter,
          translate: `0px ${interpolate(enter, [0, 1], [8, 0])}px`,
        }}
      >
        {page.tokens.map((tok, i) => {
          const active = tok.fromMs <= now && tok.toMs > now;
          const spoken = tok.fromMs <= now;
          const key = tok.text.trim().toLowerCase().replace(/[^\p{L}\p{N}.]/gu, "");
          const isEm = emphasis.has(key);
          const pop = isEm ? interpolate(now - tok.fromMs, [0, 90, 220], [1, 1.12, 1], clamp) : 1;
          return (
            <span
              key={`${tok.fromMs}-${i}`}
              style={{
                color: active || (isEm && spoken) ? C.amber : spoken ? C.text : "rgba(242,239,232,0.55)",
                display: "inline-block",
                scale: `${pop}`,
              }}
            >
              {tok.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** Word-synced captions from the VO timing map (script spelling, Whisper timing). */
export const Captions: React.FC<{ emphasis: string[] }> = ({ emphasis }) => {
  const { fps } = useVideoConfig();
  const em = useMemo(() => new Set(emphasis.flatMap((e) => e.toLowerCase().split(/\s+/)).map((w) => w.replace(/[^\p{L}\p{N}.]/gu, ""))), [emphasis]);
  const pages = useMemo(() => {
    const words = T.words as { text: string; line: string; startMs: number; endMs: number }[];
    const caps: (Caption & { pageBreakAfter?: boolean })[] = words.map((w, i) => ({
      text: (i === 0 ? "" : " ") + w.text,
      startMs: w.startMs,
      endMs: w.endMs,
      timestampMs: w.startMs,
      confidence: null,
      pageBreakAfter: words[i + 1]?.line !== w.line,
    }));
    return createTikTokStyleCaptions({ captions: caps, combineTokensWithinMilliseconds: SWITCH_MS }).pages;
  }, []);
  return (
    <AbsoluteFill>
      {pages.map((page, i) => {
        const next = pages[i + 1];
        const from = Math.round((page.startMs / 1000) * fps);
        const last = page.tokens[page.tokens.length - 1].toMs;
        const until = Math.round((Math.min(next ? next.startMs : Infinity, last + 400) / 1000) * fps);
        if (until <= from) return null;
        return (
          <Sequence key={i} from={from} durationInFrames={until - from} name={`Caption ${i}`}>
            <Page page={page} emphasis={em} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
