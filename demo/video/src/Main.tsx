import { Audio, Video } from "@remotion/media";
import { AbsoluteFill, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Background } from "./components/Background";
import { Captions } from "./components/Captions";
import { Callout, Chip, KineticTitle } from "./components/Cards";
import { Window, type CursorKey, type ZoomKey } from "./components/Window";
import flows from "./data/flows2.json";
import glimmer from "./data/glimmer.json";
import { C, EASE, FPS, T, at, body, clamp, display, emph, mono } from "./theme";

type Box = [number, number, number, number];
type Flow = keyof typeof flows;
const norm = (s: string) => s.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
/** Frame where `word` is spoken inside line `id` (from the VO timing map). */
const wordAt = (id: string, word: string) => {
  const w = (T.words as { text: string; line: string; startMs: number }[]).find((x) => x.line === id && norm(x.text).startsWith(norm(word)));
  return w ? Math.round((w.startMs / 1000) * FPS) : at(id);
};

/**
 * A captured UI flow placed on the timeline. Clip time `trim`..end is stretched (never faster than 1x,
 * never slower than 0.4x) to fill the scene; zoom and cursor keys are given in CLIP seconds and mapped here.
 */
const FlowScene: React.FC<{
  flow: Flow; trim: number; len: number; zoom?: { t: number; box: Box | null; pad?: number }[];
  cursor?: { t: number; x: number; y: number; click?: boolean }[]; children?: React.ReactNode;
}> = ({ flow, trim, len, zoom = [], cursor = [], children }) => {
  const clipLen = flows[flow].duration_s - trim - 0.1;
  const rate = Math.min(1, Math.max(0.4, clipLen / (len / FPS)));
  const local = (t: number) => Math.round(((t - trim) / rate) * FPS);
  const z: ZoomKey[] = zoom.map((k) => ({ at: Math.max(0, local(k.t)), box: k.box, pad: k.pad }));
  const c: CursorKey[] = cursor.map((k) => ({ at: Math.max(0, local(k.t)), x: k.x, y: k.y, click: k.click }));
  return (
    <AbsoluteFill>
      <Window src={`flows2/flow_${flow}.mp4`} trimBeforeSec={trim} rate={rate} zoom={z} cursor={c} />
      {children}
    </AbsoluteFill>
  );
};

// Region boxes are the c2 manifest's model outputs / label geometry in the 960x540 clip.
const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const k = interpolate(frame, [0, 300], [1.0, 1.08]);
  const boxAt = (f: number) => interpolate(frame, [f, f + 8], [0, 1], { ...clamp, easing: EASE });
  const nameF = emph("h1", "name"), bldF = emph("h1", "building"), numF = emph("h1", "phone number");
  const box = (b: Box, f: number, label: string) => (
    <div style={{ position: "absolute", left: b[0] * 2, top: b[1] * 2, width: b[2] * 2, height: b[3] * 2, border: `5px solid ${C.amber}`, borderRadius: 10, opacity: boxAt(f), scale: `${interpolate(boxAt(f), [0, 1], [1.15, 1])}` }}>
      <div style={{ position: "absolute", top: -58, left: 0, fontFamily: mono, fontSize: 34, color: C.bg, background: C.amber, padding: "4px 12px", borderRadius: 6 }}>{label}</div>
    </div>
  );
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ scale: `${k}` }}>
        <Video src={staticFile("clips/c2_input.mp4")} muted trimBefore={5 * FPS} style={{ width: 1920, height: 1080 }} />
        {box([280, 28, 400, 92], nameF, "name")}
        {box([680, 392, 250, 64], bldF, "building + flat")}
      </AbsoluteFill>
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(11,13,16,0) 35%, rgba(11,13,16,0.94) 82%)" }} />
      <KineticTitle top={700} size={110} words={[{ text: "Name.", at: nameF }, { text: "Building.", at: bldF }, { text: "Number.", at: numF, accent: true }]} />
      <Chip text="fictional data · composited clip" at={at("h2") - at("h1")} x={70} y={60} />
    </AbsoluteFill>
  );
};

// v3 scenes. Every number is from a committed artifact (see demo/script.md evidence column).
const ImpactCard: React.FC = () => {
  const frame = useCurrentFrame();
  const o = at("i1");
  const bars = [
    { label: "Full name", sample: "“Rohan Kulkarni”", secs: 23.3, at: emph("i1", "twenty-three") - o },
    { label: "Surname + flat number", sample: "“KULKARNI — 12”", secs: 22.3, at: emph("i1", "twenty-two") - o },
  ];
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ opacity: 0.16, filter: "blur(2px)" }}><Video src={staticFile("clips/c2_input.mp4")} muted trimBefore={5 * FPS} style={{ width: 1920, height: 1080 }} /></AbsoluteFill>
      <AbsoluteFill style={{ background: "linear-gradient(90deg, rgba(11,13,16,0.92) 0%, rgba(11,13,16,0.7) 100%)" }} />
      <AbsoluteFill style={{ justifyContent: "center", padding: "0 180px", gap: 54 }}>
        <div style={{ fontFamily: display, fontWeight: 700, fontSize: 84, color: C.text, opacity: interpolate(frame, [0, 10], [0, 1], clamp) }}>On screen, in a 25-second clip:</div>
        {bars.map((b) => {
          const p = interpolate(frame, [b.at, b.at + 26], [0, b.secs / 25], { ...clamp, easing: EASE });
          return (
            <div key={b.label} style={{ display: "grid", gap: 14, opacity: interpolate(frame, [b.at - 6, b.at + 4], [0, 1], clamp) }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontFamily: body, fontSize: 40, color: C.text }}>
                <span><b>{b.label}</b> <span style={{ color: C.dim, fontFamily: mono, fontSize: 32 }}>{b.sample}</span></span>
                <span style={{ fontFamily: mono, color: C.amber }}>{(p * 25).toFixed(1)} s</span>
              </div>
              <div style={{ height: 22, borderRadius: 11, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
                <div style={{ width: `${p * 100}%`, height: "100%", background: C.amber, borderRadius: 11 }} />
              </div>
            </div>
          );
        })}
        <div style={{ fontFamily: mono, fontSize: 24, color: C.dim }}>Measured from Veil's track spans on the real run (runs-rep/r1/c2). Fictional data.</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const DetectorsCard: React.FC = () => {
  const frame = useCurrentFrame();
  const o = at("p1");
  const show = (f: number) => ({ opacity: interpolate(frame, [f, f + 10], [0, 1], clamp), translate: `0px ${interpolate(frame, [f, f + 14], [24, 0], { ...clamp, easing: EASE })}px` });
  const zeroF = emph("p1", "zero of four") - o, veilF = at("p2") - o, allF = emph("p2", "all four") - o;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 40, width: 1560 }}>
        <div style={{ padding: 48, borderRadius: 28, background: C.panel, border: `1px solid ${C.line}`, ...show(0) }}>
          <div style={{ fontFamily: mono, fontSize: 30, color: C.dim }}>Face & plate detectors</div>
          <div style={{ fontFamily: display, fontWeight: 700, fontSize: 200, lineHeight: 1.05, color: C.dim, ...show(zeroF) }}>0 / 4</div>
          <div style={{ fontFamily: body, fontSize: 34, color: C.dim, ...show(zeroF) }}>planted leaks found on held-out clips</div>
        </div>
        <div style={{ padding: 48, borderRadius: 28, background: C.panel, border: `2px solid ${C.amber}`, boxShadow: "0 0 80px rgba(232,176,74,0.12)", ...show(veilF) }}>
          <div style={{ fontFamily: mono, fontSize: 30, color: C.amber }}>Veil (Muse Spark + SAM 3.1)</div>
          <div style={{ fontFamily: display, fontWeight: 700, fontSize: 200, lineHeight: 1.05, color: C.text }}>
            {frame < allF ? "3 / 4" : "4 / 4"}
          </div>
          <div style={{ fontFamily: body, fontSize: 34, color: C.text }}>{frame < allF ? "first (frozen) run" : "in 2 of 3 full re-runs · 3/4 in the third"}</div>
        </div>
      </div>
      <div style={{ position: "absolute", bottom: 150, fontFamily: mono, fontSize: 24, color: C.dim }}>Sources: eval/results/final/heldout_results.md · gate/GATE_RESULT.md · gate/repeats/</div>
    </AbsoluteFill>
  );
};

type GlimmerData = { frames: number; frames_ok: number; median_s: number | null; tok_s: number | null; proposals: { frame: number; concept: string; why: string }[]; result: string | null; quant: string };
const GlimmerScene: React.FC<{ g: GlimmerData }> = ({ g }) => {
  const frame = useCurrentFrame();
  const o = at("g1");
  const show = (f: number) => ({ opacity: interpolate(frame, [f, f + 10], [0, 1], clamp), translate: `0px ${interpolate(frame, [f, f + 14], [20, 0], { ...clamp, easing: EASE })}px` });
  const neverF = emph("g1", "never leave") - o;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ width: 1640, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 36 }}>
        <div style={{ borderRadius: 20, background: "#0E1014", border: `1px solid ${C.line}`, padding: "28px 32px", fontFamily: mono, fontSize: 24, lineHeight: 1.6, color: C.dim, ...show(0) }}>
          <div style={{ color: C.amber, marginBottom: 12 }}>● this laptop · Apple M4 Pro · no upload</div>
          <div><span style={{ color: C.green }}>$ </span><span style={{ color: C.text }}>llama-server -m Muse-Glimmer-30B ({g.quant})</span></div>
          <div style={{ color: C.text }}>  --mmproj vision  --port 8088</div>
          <div><span style={{ color: C.green }}>$ </span><span style={{ color: C.text }}>VEIL_DISCOVER=glimmer veil run c2.mp4</span></div>
          <div style={{ marginTop: 14 }}>{g.frames_ok} of {g.frames} keyframes answered (rest timed out) · median {g.median_s?.toFixed(0)} s each · {g.tok_s?.toFixed(1)} tokens/s</div>
          <div>same prompt, same JSON schema, same scorer as hosted Spark</div>
          {g.result && <div style={{ marginTop: 14, color: C.text }}>{g.result}</div>}
        </div>
        <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
          <div style={{ fontFamily: display, fontWeight: 700, fontSize: 56, color: C.text, ...show(4) }}>Muse Glimmer proposed, locally:</div>
          {g.proposals.slice(0, 4).map((p, i) => (
            <div key={i} style={{ padding: "16px 20px", borderRadius: 14, background: C.panel, border: `1px solid ${C.amber}`, ...show(14 + i * 8) }}>
              <div style={{ fontFamily: body, fontWeight: 700, fontSize: 30, color: C.amber }}>{p.concept} <span style={{ fontFamily: mono, fontSize: 22, color: C.dim }}>· frame {p.frame}</span></div>
              <div style={{ fontFamily: body, fontSize: 24, color: C.text }}>“{p.why}”</div>
            </div>
          ))}
          <div style={{ fontFamily: mono, fontSize: 26, color: C.green, ...show(neverF) }}>keyframes processed on-device for this stage</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const STAGE_TRACKS: Box = [160, 120, 1390, 1100];
const FINDINGS_COL: Box = [1585, 770, 815, 670];

export const Main: React.FC = () => {
  const sc = (a: string, b: string | null) => ({ from: Math.max(0, at(a)), durationInFrames: (b ? at(b) : T.total) - Math.max(0, at(a)) });
  const S = {
    hook: sc("h1", "i1"), impact: sc("i1", "p1"), det: sc("p1", "a1"), hero: sc("a1", "a2"), aha: sc("a2", "a3"), tracks: sc("a3", "f1"),
    find: sc("f1", "f2"), mask: sc("f2", "n1"), nat: sc("n1", "v1"), voice: sc("v1", "g1"), glim: sc("g1", "r1"), pay: sc("r1", "e1"), ev: sc("e1", "c0"),
    cta: sc("c0", "c1"), outro: sc("c1", null),
  };
  const allEmph = (T as unknown as { emph: Record<string, Record<string, number>> }).emph;
  const emphasis = Object.values(allEmph).flatMap((o) => Object.keys(o));
  const rel = (f: number, s: { from: number }) => f - s.from;
  const sec = (id: string, s: { from: number }) => (at(id) - s.from) / FPS;
  const evSplit = wordAt("e1", "full") - S.ev.from;

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Background />
      <Sequence name="Hook" {...S.hook}><Hook /></Sequence>
      <Sequence name="Impact" {...S.impact}><ImpactCard /></Sequence>
      <Sequence name="Detectors vs Veil" {...S.det}><DetectorsCard /></Sequence>

      <Sequence name="Site hero" {...S.hero}>
        <FlowScene flow="hero" trim={1.0} len={S.hero.durationInFrames}
          zoom={[{ t: 1.0, box: null }, { t: 2.3, box: [1150, 560, 1300, 900] }]}
          cursor={[{ t: 1.0, x: 2300, y: 1300 }, { t: 2.4, x: 1990, y: 1009, click: true }, { t: 5.96, x: 1556, y: 1009 }, { t: 9.2, x: 2159, y: 1009 }]}>
          <Chip text="thecodekaizen.github.io/veil · real pipeline output" at={0} x={150} y={14} color={C.amber} />
        </FlowScene>
      </Sequence>
      <Sequence name="Aha: discovery" {...S.aha}>
        <FlowScene flow="desk_play" trim={1.1} len={S.aha.durationInFrames} zoom={[{ t: 1.1, box: STAGE_TRACKS }]}>
          <Sequence from={rel(wordAt("a2", "notification"), S.aha)}>
            <Callout x={1210} y={150} at={0} text="Spark: message notification banner" sub="“Shows full personal name of associated contact, identifying who filmed or their associate”" />
          </Sequence>
          <Sequence from={rel(wordAt("a2", "gold"), S.aha)}>
            <Callout x={1210} y={520} at={0} text="Spark: black gold nameplate" sub="“Contains surname Kulkarni with number, potentially vehicle plate or personal identifier”" />
          </Sequence>
        </FlowScene>
      </Sequence>
      <Sequence name="Aha: tracking" {...S.tracks}>
        <FlowScene flow="desk_tracks" trim={1.4} len={S.tracks.durationInFrames} zoom={[{ t: 1.4, box: [160, 100, 1400, 960] }]}
          cursor={[{ t: 1.4, x: 1300, y: 1100 }, { t: 2.46, x: 852, y: 720, click: true }]}>
          <Chip text="SAM 3.1 masks → covers in the exported file" at={6} x={150} y={14} color={C.amber} />
        </FlowScene>
      </Sequence>
      <Sequence name="Verify: covers" {...S.find}>
        <FlowScene flow="desk_checks" trim={1.0} len={S.find.durationInFrames} zoom={[{ t: 1.0, box: FINDINGS_COL }]} />
      </Sequence>
      <Sequence name="Mask check" {...S.mask}>
        <FlowScene flow="desk_mask" trim={2.6} len={S.mask.durationInFrames}
          zoom={[{ t: 2.6, box: [160, 120, 2240, 1100] }, { t: 2.6 + sec("f3", S.mask) * 0.9, box: [160, 180, 2240, 450], pad: 1.15 }]}
          cursor={[{ t: 2.6, x: 1900, y: 1200 }, { t: 3.39, x: 1280, y: 250 }]}>
          <Sequence from={rel(wordAt("f3", "found"), S.mask)}>
            <Callout x={1150} y={640} at={0} color={C.red} text="Rejected: 3 masks held code" sub="OCR read “def total(items):”. Spark claimed “KULKARNI”. Removed before redaction." />
          </Sequence>
        </FlowScene>
      </Sequence>
      <Sequence name="Natural export" {...S.nat}>
        <FlowScene flow="desk_natural" trim={3.6} len={S.nat.durationInFrames}
          zoom={[{ t: 3.6, box: [160, 740, 1400, 700] }]}
          cursor={[{ t: 3.6, x: 1100, y: 1100 }, { t: 4.74, x: 387, y: 808, click: true }, { t: 5.9, x: 2700, y: 900 }]}>
          <Sequence from={rel(wordAt("n1", "fictional"), S.nat)}>
            <Callout x={1220} y={170} at={0} text="Natural export · audited" sub="“Rohan Kulkarni” → “Aarav Sharma” · “KULKARNI — 12” → “SHARMA - 87”. OCR on the natural file: 0 original words in 53 frames." />
          </Sequence>
        </FlowScene>
      </Sequence>
      <Sequence name="Voice" {...S.voice}>
        <FlowScene flow="desk_voice" trim={2.6} len={S.voice.durationInFrames}
          zoom={[{ t: 2.6, box: [160, 860, 1400, 580] }, { t: 2.6 + (wordAt("v1", "mutes") - S.voice.from) / FPS * 0.6, box: [1585, 960, 815, 380] }]} />
      </Sequence>
      <Sequence name="Open weights (Glimmer)" {...S.glim}><GlimmerScene g={glimmer as GlimmerData} /></Sequence>
      <Sequence name="Payoff: verdict" {...S.pay}>
        <FlowScene flow="desk_verdict" trim={3.6} len={S.pay.durationInFrames}
          zoom={[{ t: 3.6, box: [160, 480, 2240, 280], pad: 1.1 }, { t: 3.6 + (wordAt("r1", "shows") - S.pay.from) / FPS * 0.5, box: FINDINGS_COL }]} />
      </Sequence>
      <Sequence name="Evidence: ledger" from={S.ev.from} durationInFrames={evSplit}>
        <FlowScene flow="site_ledger" trim={3.1} len={evSplit} zoom={[{ t: 3.1, box: [160, 160, 2240, 840], pad: 1.05 }]} />
      </Sequence>
      <Sequence name="Evidence: results" from={S.ev.from + evSplit} durationInFrames={S.ev.durationInFrames - evSplit}>
        <FlowScene flow="site_results" trim={2.2} len={S.ev.durationInFrames - evSplit} zoom={[{ t: 2.2, box: [162, 120, 2236, 1000], pad: 1.04 }]} />
      </Sequence>
      <Sequence name="CTA (live site)" {...S.cta}>
        <FlowScene flow="site_cta" trim={1.9} len={S.cta.durationInFrames} zoom={[{ t: 1.9, box: null }]}
          cursor={[{ t: 1.9, x: 1800, y: 1200 }, { t: 2.97, x: 1061, y: 743 }]}>
          <Chip text="thecodekaizen.github.io/veil" at={0} x={150} y={14} color={C.amber} />
        </FlowScene>
      </Sequence>
      <Sequence name="Outro" {...S.outro}><Outro /></Sequence>

      <Captions emphasis={emphasis} />
      <Audio src={staticFile("vo.wav")} />
    </AbsoluteFill>
  );
};

const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const p = (f: number) => ({ opacity: interpolate(frame, [f, f + 12], [0, 1], clamp), translate: `0px ${interpolate(frame, [f, f + 14], [20, 0], { ...clamp, easing: EASE })}px` });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 26 }}>
      <div style={{ fontFamily: mono, fontSize: 40, color: C.dim, ...p(0) }}>Models propose. <span style={{ color: C.amber }}>Code decides.</span></div>
      <div style={{ fontFamily: display, fontWeight: 700, fontSize: 220, color: C.text, lineHeight: 1, ...p(0) }}>Veil</div>
      <div style={{ display: "flex", gap: 18, ...p(8) }}>
        {["Muse Spark 1.3", "SAM 3.1", "Muse Voice Transcribe", "Muse Glimmer (local)"].map((m) => (
          <div key={m} style={{ fontFamily: mono, fontSize: 32, color: C.amber, border: `1px solid ${C.amber}`, borderRadius: 999, padding: "8px 22px" }}>{m}</div>
        ))}
      </div>
      <div style={{ fontFamily: body, fontSize: 44, fontWeight: 600, color: C.text, marginTop: 16, ...p(14) }}>thecodekaizen.github.io/veil</div>
      <div style={{ fontFamily: mono, fontSize: 30, color: C.dim, ...p(20) }}>github.com/thecodekaizen/veil</div>
      <div style={{ position: "absolute", bottom: 150, width: 1500, textAlign: "center", fontFamily: body, fontSize: 22, lineHeight: 1.4, color: C.dim, ...p(10) }}>
        Street footage: Subhashish Panigrahi (Cuttack) and Fowler&amp;fowler (Delhi), Wikimedia Commons, CC BY-SA 3.0, composited with fictional graphics.
        Narration: AI voice (Kokoro TTS). All results from committed run artifacts.
      </div>
    </AbsoluteFill>
  );
};
