// Veil demo v4: story-first (demo/STORYBOARD_v4.md). Every zoom, highlight and headline is keyed to a word of the narration
// (Whisper word timestamps in data/timeline.json). Zooms: ease-in-out 500 ms, hold until a hard cut, never zoom back out.
import { Audio, Video } from "@remotion/media";
import { AbsoluteFill, Easing, Img, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Background } from "./components/Background";
import { Captions } from "./components/Captions";
import { Callout } from "./components/Cards";
import { Window, type ZoomKey } from "./components/Window";
import boxes from "./data/c2_boxes.json";
import flows from "./data/flows2.json";
import glimmer from "./data/glimmer.json";
import { C, EASE, FPS, T, at, body, clamp, display, mono } from "./theme";

type Box = [number, number, number, number];
type Flow = keyof typeof flows;
const norm = (s: string) => s.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
/** Absolute frame where `word` is spoken inside line `id`. Throws if the word isn't in the line (keeps cues honest). */
const wordAt = (id: string, word: string) => {
  const w = (T.words as { text: string; line: string; startMs: number }[]).find((x) => x.line === id && norm(x.text).startsWith(norm(word)));
  if (!w) throw new Error(`word "${word}" not found in line ${id}`);
  return Math.round((w.startMs / 1000) * FPS);
};
const ZOOM_EASE = Easing.inOut(Easing.cubic);
const ZOOM_FRAMES = 15; // 500 ms

/** A captured UI flow. `frame0` is the framing for the whole shot (static); `zooms` start on absolute narration frames. */
const FlowScene: React.FC<{
  flow: Flow; trim: number; from: number; len: number; frame0: Box | null; zooms?: { at: number; box: Box; pad?: number }[];
  children?: React.ReactNode;
}> = ({ flow, trim, from, len, frame0, zooms = [], children }) => {
  const clipLen = flows[flow].duration_s - trim - 0.1;
  const rate = Math.min(1, Math.max(0.4, clipLen / (len / FPS)));
  const z: ZoomKey[] = [{ at: 0, box: frame0, pad: 1.04 }, ...zooms.map((k) => ({ at: k.at - from, box: k.box, pad: k.pad ?? 1.1 }))];
  return (
    <AbsoluteFill>
      <Window src={`flows2/flow_${flow}.mp4`} trimBeforeSec={trim} rate={rate} zoom={z} />
      {children}
    </AbsoluteFill>
  );
};

/** A 960x540 source clip shown full frame (1920x1080) with an optional zoom and overlay boxes in source pixels. */
const FullClip: React.FC<{ src: string; startSec: number; zoom?: { at: number; box: Box }; overlays?: { box: Box; at: number; color: string; label?: string }[] }> = ({ src, startSec, zoom, overlays = [] }) => {
  const frame = useCurrentFrame();
  const S = 2; // 960 -> 1920
  let cx = 480, cy = 270, s = 1;
  if (zoom) {
    const [x, y, w, h] = zoom.box;
    const ts = Math.min(2.6, Math.min(960 / (w * 1.25), 540 / (h * 1.25)));
    const tx = Math.min(960 - 480 / ts, Math.max(480 / ts, x + w / 2)), ty = Math.min(540 - 270 / ts, Math.max(270 / ts, y + h / 2));
    const p = interpolate(frame, [zoom.at, zoom.at + ZOOM_FRAMES], [0, 1], { ...clamp, easing: ZOOM_EASE });
    cx = 480 + (tx - 480) * p; cy = 270 + (ty - 270) * p; s = Math.pow(ts, p);
  }
  const k = S * s, ox = 960 - cx * k, oy = 540 - cy * k;
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: 960, height: 540, transformOrigin: "0 0", transform: `translate(${ox}px, ${oy}px) scale(${k})` }}>
        <Video src={staticFile(src)} muted trimBefore={Math.round(startSec * FPS)} style={{ width: 960, height: 540 }} />
        {overlays.map((o, i) => {
          const p = interpolate(frame, [o.at, o.at + 9], [0, 1], { ...clamp, easing: EASE });
          const [x1, y1, x2, y2] = o.box;
          return (
            <div key={i} style={{ position: "absolute", left: x1, top: y1, width: x2 - x1, height: y2 - y1, border: `3px solid ${o.color}`, borderRadius: 6, opacity: p, scale: `${1.12 - 0.12 * p}` }}>
              {o.label && <div style={{ position: "absolute", top: -26, left: -3, background: o.color, color: C.bg, font: `700 15px ${mono}`, padding: "3px 8px", borderRadius: 4, whiteSpace: "nowrap" }}>{o.label}</div>}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

type HeadItem = { at: number; text: React.ReactNode; tone?: "amber" | "red" | "green" | "text" };
/** Beat headline (top band): carries the meaning when muted. */
const Headline: React.FC<{ items: HeadItem[]; bottom?: boolean }> = ({ items, bottom }) => {
  const frame = useCurrentFrame();
  const cur = [...items].reverse().find((i) => frame >= i.at);
  if (!cur) return null;
  const p = interpolate(frame, [cur.at, cur.at + 8], [0, 1], { ...clamp, easing: EASE });
  const col = cur.tone === "red" ? C.red : cur.tone === "green" ? C.green : cur.tone === "amber" ? C.amber : C.text;
  return (
    <div style={{ position: "absolute", left: 60, right: 60, ...(bottom ? { bottom: 150 } : { top: 26 }), display: "flex", justifyContent: "flex-start" }}>
      <div style={{ font: `700 ${bottom ? 54 : 40}px ${body}`, color: col, background: "rgba(11,13,16,0.9)", padding: bottom ? "14px 26px" : "12px 22px", borderRadius: 14, opacity: p, translate: `0px ${(1 - p) * 10}px`, maxWidth: 1800 }}>{cur.text}</div>
    </div>
  );
};

const Fineprint: React.FC = () => (
  <div style={{ position: "absolute", right: 28, bottom: 18, font: `500 20px ${mono}`, color: "rgba(242,239,232,0.75)", background: "rgba(11,13,16,0.6)", padding: "4px 10px", borderRadius: 6 }}>
    Demo clips: composited, fictional data
  </div>
);

const NOTIF = boxes.notification as Box;
const DOOR = boxes.door as Box;
const plateAt = (f: number): Box => {
  const pb = boxes.plate_by_frame as Record<string, number[]>;
  for (let d = 0; d < 40; d++) for (const k of [f + d, f - d]) if (pb[String(k)]) return pb[String(k)] as Box;
  return [640, 230, 700, 285];
};
const toXYWH = (b: Box): Box => [b[0], b[1], b[2] - b[0], b[3] - b[1]];

// ---- scenes ----------------------------------------------------------------------------------------------------------
const Hook: React.FC<{ from: number }> = ({ from }) => {
  const nameF = wordAt("h2", "full") - from, flatF = wordAt("h2", "flat") - from;
  return (
    <AbsoluteFill>
      <FullClip src="clips/c2_input.mp4" startSec={5} overlays={[
        { box: NOTIF, at: nameF, color: C.amber, label: "full name" },
        { box: DOOR, at: flatF, color: C.amber, label: "flat number" },
      ]} />
      <Headline bottom items={[
        { at: 0, text: "About to be posted." },
        { at: nameF, text: <>It leaks: <span style={{ color: C.amber }}>① a full name</span></> },
        { at: flatF, text: <>It leaks: <span style={{ color: C.amber }}>① a full name ② a flat number</span></> },
      ]} />
    </AbsoluteFill>
  );
};

const FIXED_AT_ONE = 0.3; // clip seconds shown on "one": the standard tool's car-plate cover is on screen (track frames 0-41 of runs/c2demo)
const Contrast: React.FC<{ from: number }> = ({ from }) => {
  const oneF = wordAt("x1", "one") - from;
  const clipFrame = Math.round(FIXED_AT_ONE * 25 + 8);
  return (
    <AbsoluteFill>
      <Sequence durationInFrames={oneF} layout="none"><FullClip src="clips/c2_fixed.mp4" startSec={24.9 - oneF / FPS} /></Sequence>
      <Sequence from={oneF} layout="none"><FullClip src="clips/c2_fixed.mp4" startSec={FIXED_AT_ONE} zoom={{ at: 0, box: toXYWH(plateAt(clipFrame)) }} /></Sequence>
      <Headline bottom items={[{ at: 0, text: "Standard detection: faces · plates · screens · documents" }, { at: oneF, text: "Standard detection covered: one car's plate" }]} />
    </AbsoluteFill>
  );
};
const ContrastMiss: React.FC<{ clipAt: number }> = ({ clipAt }) => (
  <AbsoluteFill>
    <FullClip src="clips/c2_fixed.mp4" startSec={clipAt} overlays={[
      { box: NOTIF, at: 0, color: C.red, label: "still exposed" },
      { box: DOOR, at: 0, color: C.red, label: "still exposed" },
    ]} />
    <Headline bottom items={[{ at: 0, text: <>Standard detection: <span style={{ color: C.red }}>both still exposed</span> <span style={{ color: C.dim, fontSize: 28 }}>· 0 of 4 across 3 test clips</span></> }]} />
  </AbsoluteFill>
);

const OneLiner: React.FC<{ from: number }> = ({ from }) => {
  const frame = useCurrentFrame();
  const splitF = wordAt("o1", "not") - from;
  const coversF = wordAt("o1", "covers") - from;
  const titleOut = interpolate(frame, [splitF - 6, splitF], [1, 0], clamp);
  const pane = (src: string, label: string, color: string, zoom?: { at: number; box: Box }) => (
    <div style={{ position: "relative", width: 930, height: 523, borderRadius: 18, overflow: "hidden", border: `3px solid ${color}`, boxShadow: "0 30px 80px rgba(0,0,0,0.5)" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1920, height: 1080, scale: `${930 / 1920}`, transformOrigin: "0 0" }}>
        <FullClip src={src} startSec={7} zoom={zoom} />
      </div>
      <div style={{ position: "absolute", left: 14, bottom: 14, font: `700 28px ${body}`, color: C.bg, background: color, padding: "6px 14px", borderRadius: 8 }}>{label}</div>
    </div>
  );
  return (
    <AbsoluteFill>
      <Sequence durationInFrames={splitF} layout="none">
        <AbsoluteFill style={{ opacity: titleOut }}><Video src={staticFile("clips/hf-sting.mp4")} muted style={{ width: 1920, height: 1080 }} /></AbsoluteFill>
      </Sequence>
      <Sequence from={splitF} layout="none">
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
          <div style={{ display: "flex", gap: 24, marginTop: 40 }}>
            {pane("clips/c2_fixed.mp4", "Standard detection", C.red)}
            {pane("clips/c2_output_r1.mp4", "Veil", C.green, { at: coversF - splitF, box: [600, 350, 380, 150] })}
          </div>
        </AbsoluteFill>
        <Headline items={[{ at: 0, text: <>Veil: finds what identifies you, <span style={{ color: C.amber }}>not just faces and plates</span></> }]} />
      </Sequence>
    </AbsoluteFill>
  );
};


/** Natural mode: the same shot, input -> natural export, revealed by a wipe on "fictional"; zoom onto the name. */
const NaturalScene: React.FC<{ from: number }> = ({ from }) => {
  const frame = useCurrentFrame();
  const fictF = wordAt("nx", "fictional") - from, realF = wordAt("nx", "real") - from;
  const p = interpolate(frame, [fictF, fictF + 24], [0, 100], { ...clamp, easing: ZOOM_EASE });
  const zoom = { at: fictF + 30, box: [250, 10, 460, 140] as Box };
  return (
    <AbsoluteFill>
      <FullClip src="clips/c2_input.mp4" startSec={6} zoom={zoom} />
      <AbsoluteFill style={{ clipPath: `inset(0 ${100 - p}% 0 0)` }}><FullClip src="clips/c2_natural.mp4" startSec={6} zoom={zoom} /></AbsoluteFill>
      {p > 0 && p < 100 && <div style={{ position: "absolute", top: 0, bottom: 0, left: `${p}%`, width: 4, background: "#fff" }} />}
      <Headline bottom items={[
        { at: 0, text: <>Natural mode: <span style={{ color: C.amber }}>no black boxes</span></> },
        { at: fictF, text: <>Natural mode: <span style={{ color: C.amber }}>a fictional name, same font and colour</span></> },
        { at: realF, text: <>The video still looks real · <span style={{ color: C.green }}>re-audited: 0 original words left</span></> },
      ]} />
    </AbsoluteFill>
  );
};

/** Muse Image erase on a still: input frame -> erased frame, wipe on "erases". */
const EraseScene: React.FC<{ from: number }> = ({ from }) => {
  const frame = useCurrentFrame();
  const erF = wordAt("ex", "erases") - from, behindF = wordAt("ex", "behind") - from;
  const p = interpolate(frame, [erF, erF + 30], [0, 100], { ...clamp, easing: ZOOM_EASE });
  const img = (src: string) => <Img src={staticFile(src)} style={{ position: "absolute", inset: 0, width: 1920, height: 1080 }} />;
  return (
    <AbsoluteFill>
      {img("clips/erase_in.png")}
      <AbsoluteFill style={{ clipPath: `inset(0 ${100 - p}% 0 0)` }}>{img("clips/erase_out.png")}</AbsoluteFill>
      {p > 0 && p < 100 && <div style={{ position: "absolute", top: 0, bottom: 0, left: `${p}%`, width: 4, background: "#fff" }} />}
      <Headline bottom items={[
        { at: 0, text: <>Still photo: <span style={{ color: C.amber }}>Muse Image</span></> },
        { at: erF, text: <><span style={{ color: C.amber }}>Muse Image</span> erases it, and rebuilds what was behind</> },
        { at: behindF, text: <>Re-checked with OCR: <span style={{ color: C.green }}>nothing readable left</span></> },
      ]} />
    </AbsoluteFill>
  );
};

/** One job per Meta model, with its measured impact. */
const ModelsCard: React.FC<{ from: number }> = ({ from }) => {
  const frame = useCurrentFrame();
  const show = (f: number) => ({ opacity: interpolate(frame, [f, f + 10], [0, 1], clamp), translate: `0px ${interpolate(frame, [f, f + 14], [16, 0], { ...clamp, easing: EASE })}px` });
  const rows: { at: number; model: string; job: string; impact: string; open?: boolean }[] = [
    { at: wordAt("m1", "spark") - from, model: "Muse Spark 1.3", job: "Finds what identifies you in this video, with a reason", impact: "without it: 0 of 4 found · with it: 3 of 4" },
    { at: wordAt("m1", "sam") - from, model: "SAM 3.1", job: "Turns each finding into a mask, tracked through every frame", impact: "without it: nothing is tracked or covered" },
    { at: wordAt("m1", "voice") - from, model: "Muse Voice Transcribe", job: "Hears spoken numbers in Hindi or English", impact: "without it: the number goes out unmuted" },
    { at: wordAt("m1", "image") - from, model: "Muse Image", job: "Erases what was found from a still, rebuilds the background", impact: "without it: black boxes only" },
    { at: wordAt("m1", "without") - from, model: "Muse Glimmer 30B · open weights", job: "Same discovery as Spark, on this laptop", impact: "frames never uploaded · $0", open: true },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ width: 1720, display: "grid", gap: 16, marginTop: 30 }}>
        {rows.map((r, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "520px 1fr", gap: 30, alignItems: "center", padding: "20px 30px", borderRadius: 16,
            background: C.panel, border: `2px solid ${r.open ? C.green : C.amber}`, ...show(r.at) }}>
            <div style={{ font: `700 40px ${body}`, color: r.open ? C.green : C.amber }}>{r.model}</div>
            <div>
              <div style={{ font: `600 32px ${body}`, color: C.text }}>{r.job}</div>
              <div style={{ font: `500 25px ${mono}`, color: C.dim, marginTop: 4 }}>{r.impact}</div>
            </div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const STAGE: Box = [160, 120, 1390, 1100];
const FINDINGS_COL: Box = [1585, 770, 815, 670];

type GlimmerData = { frames: number; frames_ok: number; median_s: number | null; tok_s: number | null; proposals: { frame: number; concept: string; why: string }[]; result: string | null; quant: string };
const GlimmerScene: React.FC<{ g: GlimmerData; from: number }> = ({ g, from }) => {
  const frame = useCurrentFrame();
  const show = (f: number) => ({ opacity: interpolate(frame, [f, f + 10], [0, 1], clamp), translate: `0px ${interpolate(frame, [f, f + 14], [20, 0], { ...clamp, easing: EASE })}px` });
  const neverF = wordAt("g1", "never") - from, bothF = wordAt("g2", "both") - from;
  const z = interpolate(frame, [neverF, neverF + ZOOM_FRAMES], [1, 1.45], { ...clamp, easing: ZOOM_EASE });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ width: 1680, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 36, marginTop: 40 }}>
        <div style={{ borderRadius: 20, background: "#0E1014", border: `1px solid ${C.line}`, padding: "30px 34px", fontFamily: mono, fontSize: 26, lineHeight: 1.6, color: C.dim, ...show(0) }}>
          <div style={{ color: C.amber, marginBottom: 14, fontSize: 30, scale: `${z}`, transformOrigin: "0 50%", fontWeight: 600 }}>● this laptop · no upload</div>
          <div><span style={{ color: C.green }}>$ </span><span style={{ color: C.text }}>llama-server -m Muse-Glimmer-30B</span></div>
          <div><span style={{ color: C.green }}>$ </span><span style={{ color: C.text }}>VEIL_DISCOVER=glimmer veil run c2.mp4</span></div>
          <div style={{ marginTop: 14, fontSize: 22 }}>{g.frames_ok} of {g.frames} keyframes answered · same prompt, schema and scorer as hosted Spark</div>
          <div style={{ marginTop: 18, color: C.green, fontSize: 30, fontWeight: 600, ...show(bothF) }}>On c2: found both details</div>
        </div>
        <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
          <div style={{ font: `700 50px ${display}`, color: C.text, ...show(4) }}>Muse Glimmer proposed, locally:</div>
          {g.proposals.filter((_, i) => [0, 3, 5].includes(i)).map((p, i) => (
            <div key={i} style={{ padding: "16px 20px", borderRadius: 14, background: C.panel, border: `1px solid ${C.amber}`, ...show(14 + i * 8) }}>
              <div style={{ font: `700 30px ${body}`, color: C.amber }}>{p.concept}</div>
              <div style={{ font: `500 26px ${body}`, color: C.text }}>“{p.why}”</div>
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Close: React.FC<{ from: number }> = ({ from }) => {
  const frame = useCurrentFrame();
  const p = (f: number) => ({ opacity: interpolate(frame, [f, f + 12], [0, 1], clamp) });
  const tryF = wordAt("c2", "try") - from;
  return (
    <AbsoluteFill>
      <FullClip src="clips/c2_natural.mp4" startSec={9} />
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(11,13,16,0.2) 0%, rgba(11,13,16,0.88) 58%)" }} />
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 170, gap: 14 }}>
        <div style={{ font: `700 150px ${display}`, color: C.text, lineHeight: 1, ...p(0) }}>Veil</div>
        <div style={{ font: `600 44px ${body}`, color: C.text, ...p(6) }}>Find what identifies you, and <span style={{ color: C.amber }}>fix it naturally</span>, before you post.</div>
        <div style={{ font: `700 48px ${body}`, color: C.amber, marginTop: 10, ...p(tryF) }}>thecodekaizen.github.io/veil</div>
        <div style={{ font: `500 30px ${mono}`, color: C.text, ...p(tryF + 6) }}>github.com/thecodekaizen/veil · full results, incl. failures</div>
        <div style={{ font: `500 21px ${body}`, color: C.dim, ...p(tryF + 10) }}>Muse Spark · SAM 3.1 · Muse Voice · Muse Image · Muse Glimmer (open weights) · Street footage: Subhashish Panigrahi, Fowler&amp;fowler (Wikimedia Commons, CC BY-SA 3.0) · AI narration (Kokoro) · original music</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const Main: React.FC = () => {
  const sc = (a: string, b: string | null) => ({ from: Math.max(0, at(a)), durationInFrames: (b ? at(b) : T.total) - Math.max(0, at(a)) });
  const S = {
    hook: sc("h1", "x1"), contrast: sc("x1", "o1"), one: sc("o1", "nx"), natural: sc("nx", "ex"), erase: sc("ex", "l1"), live: sc("l1", "a2"),
    find: sc("a2", "a3"), track: sc("a3", "v1"), listen: sc("v1", "v2"), confirm: sc("v2", "au"), verdict: sc("au", "r1"), unres: sc("r1", "p1"),
    proof: sc("p1", "p3"), ledger: sc("p3", "m1"), models: sc("m1", "g1"), glim: sc("g1", "c1"), close: sc("c1", null),
  };
  const missF = wordAt("x1", "misses");
  const mutesF = wordAt("v1", "mutes");
  const allEmph = (T as unknown as { emph: Record<string, Record<string, number>> }).emph;
  const emphasis = Object.values(allEmph).flatMap((o) => Object.keys(o));
  const H = (items: HeadItem[], from: number) => <Headline items={items.map((i) => ({ ...i, at: i.at - from }))} />;

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Background />
      <Sequence name="Hook" {...S.hook}><Hook from={S.hook.from} /></Sequence>
      <Sequence name="Contrast: standard tool" from={S.contrast.from} durationInFrames={missF - S.contrast.from}><Contrast from={S.contrast.from} /></Sequence>
      <Sequence name="Contrast: misses both" from={missF} durationInFrames={S.contrast.from + S.contrast.durationInFrames - missF}>
        <ContrastMiss clipAt={FIXED_AT_ONE + (missF - wordAt("x1", "one")) / FPS} />
      </Sequence>
      <Sequence name="One line + side by side" {...S.one}><OneLiner from={S.one.from} /></Sequence>
      <Sequence name="Natural mode" {...S.natural}><NaturalScene from={S.natural.from} /></Sequence>
      <Sequence name="Muse Image erase (still)" {...S.erase}><EraseScene from={S.erase.from} /></Sequence>

      <Sequence name="Live product" {...S.live}>
        <FlowScene flow="hero" trim={1.6} from={S.live.from} len={S.live.durationInFrames} frame0={null}
          zooms={[{ at: wordAt("l1", "drag"), box: [1195, 592, 1205, 678], pad: 1.02 }]} />
        {H([{ at: S.live.from, text: <>Live: <span style={{ color: C.amber }}>thecodekaizen.github.io/veil</span></> }], S.live.from)}
      </Sequence>
      <Sequence name="Find: Spark" {...S.find}>
        <FlowScene flow="desk_play" trim={1.1} from={S.find.from} len={S.find.durationInFrames} frame0={STAGE}
          zooms={[{ at: wordAt("a2", "reason"), box: [160, 120, 1390, 620] }]}>
          <Sequence from={wordAt("a2", "reason") - S.find.from}>
            <Callout x={1180} y={660} at={0} text="Spark's reason (verbatim)" sub="“Displays personal name Rohan Kulkarni in a messages notification, identifying the person associated with the video.”" />
          </Sequence>
        </FlowScene>
        {H([{ at: S.find.from, text: <>1 · Find: <span style={{ color: C.amber }}>Muse Spark</span> proposes, with a reason</> }], S.find.from)}
      </Sequence>
      <Sequence name="Find: SAM tracks" {...S.track}>
        <FlowScene flow="desk_tracks" trim={1.4} from={S.track.from} len={S.track.durationInFrames} frame0={[160, 100, 1400, 960]}
          zooms={[{ at: wordAt("a3", "every"), box: [160, 540, 1390, 440] }]} />
        {H([{ at: S.track.from, text: <><span style={{ color: C.amber }}>SAM 3.1</span> tracks each one through every frame</> }], S.track.from)}
      </Sequence>

      <Sequence name="Listen: Hindi" from={S.listen.from} durationInFrames={mutesF - S.listen.from}>
        <FlowScene flow="desk_voice" trim={2.6} from={S.listen.from} len={mutesF - S.listen.from} frame0={[160, 860, 1400, 580]}
          zooms={[{ at: wordAt("v1", "hindi"), box: [160, 1150, 1400, 290] }]} />
        {H([{ at: S.listen.from, text: <>2 · Listen: <span style={{ color: C.amber }}>Muse Voice</span> hears a number said in Hindi</> }], S.listen.from)}
      </Sequence>
      <Sequence name="Listen: muted" from={mutesF} durationInFrames={S.listen.from + S.listen.durationInFrames - mutesF}>
        <FlowScene flow="desk_voice" trim={5.0} from={mutesF} len={S.listen.from + S.listen.durationInFrames - mutesF} frame0={[160, 880, 1400, 200]} />
        {H([{ at: mutesF, text: <>Spoken number <span style={{ color: C.red }}>muted</span></> }], mutesF)}
      </Sequence>
      <Sequence name="Listen: confirm" {...S.confirm}>
        <FlowScene flow="desk_voice" trim={8.2} from={S.confirm.from} len={S.confirm.durationInFrames} frame0={[1585, 960, 815, 420]}
          zooms={[{ at: wordAt("v2", "confirm"), box: [1585, 1130, 815, 230] }]} />
        {H([{ at: S.confirm.from, text: <>Re-checked in the exported audio: <span style={{ color: C.green }}>no digits left</span></> }], S.confirm.from)}
      </Sequence>

      <Sequence name="Audit: verdict" {...S.verdict}>
        <FlowScene flow="desk_verdict" trim={3.6} from={S.verdict.from} len={S.verdict.durationInFrames} frame0={[1380, 470, 1040, 260]} />
        {H([{ at: S.verdict.from, text: "3 · Audit the exported file" }], S.verdict.from)}
      </Sequence>
      <Sequence name="Audit: unresolved" {...S.unres}>
        <FlowScene flow="desk_verdict" trim={7.7} from={S.unres.from} len={S.unres.durationInFrames} frame0={FINDINGS_COL}
          zooms={[{ at: wordAt("r1", "unresolved"), box: [1585, 770, 815, 420] }]} />
        {H([{ at: S.unres.from, text: <>COVERED · <span style={{ color: C.red }}>UNRESOLVED</span> · NOT CHECKED: never a blanket all clear</> }], S.unres.from)}
      </Sequence>
      <Sequence name="Proof (HyperFrames)" {...S.proof}><Video src={staticFile("clips/hf-proof.mp4")} muted style={{ width: 1920, height: 1080 }} /></Sequence>
      <Sequence name="Proof: ledger" {...S.ledger}>
        <FlowScene flow="site_ledger" trim={3.1} from={S.ledger.from} len={S.ledger.durationInFrames} frame0={[160, 160, 2240, 840]} />
        {H([{ at: S.ledger.from, text: "Every model call is on the ledger" }], S.ledger.from)}
      </Sequence>
      <Sequence name="Meta models: one job each" {...S.models}>
        <ModelsCard from={S.models.from} />
        {H([{ at: S.models.from, text: <>Five Meta models, <span style={{ color: C.amber }}>one job each</span></> }], S.models.from)}
      </Sequence>
      <Sequence name="Open weights" {...S.glim}>
        <GlimmerScene g={glimmer as GlimmerData} from={S.glim.from} />
        {H([{ at: S.glim.from, text: <>Open weights: <span style={{ color: C.amber }}>Muse Glimmer</span>, on this laptop</> }], S.glim.from)}
      </Sequence>
      <Sequence name="Close" {...S.close}><Close from={S.close.from} /></Sequence>

      <Captions emphasis={emphasis} />
      <Fineprint />
      <Audio src={staticFile("vo.wav")} />
    </AbsoluteFill>
  );
};
