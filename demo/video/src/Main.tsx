import { Audio, Video } from "@remotion/media";
import { AbsoluteFill, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Background } from "./components/Background";
import { Captions } from "./components/Captions";
import { Callout, Chip, GateCard, KineticTitle, StatCard, Terminal } from "./components/Cards";
import { Window, type CursorKey, type ZoomKey } from "./components/Window";
import flows from "./data/flows.json";
import wave from "../public/c3_wave.json";
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
      <Window src={`flows/flow_${flow}.mp4`} trimBeforeSec={trim} rate={rate} zoom={z} cursor={c} />
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

const Tile: React.FC<{ at: number; label: string; children: React.ReactNode }> = ({ at: a, label, children }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [a, a + 12], [0, 1], { ...clamp, easing: EASE });
  return (
    <div style={{ width: 540, opacity: p, translate: `0px ${interpolate(p, [0, 1], [40, 0])}px` }}>
      <div style={{ width: 540, height: 340, borderRadius: 18, overflow: "hidden", border: `1px solid ${C.line}`, position: "relative", background: C.panel, boxShadow: "0 30px 80px rgba(0,0,0,0.5)" }}>{children}</div>
      <div style={{ fontFamily: body, fontWeight: 600, fontSize: 40, color: C.text, marginTop: 22, textAlign: "center" }}>{label}</div>
    </div>
  );
};

/** Crop of a 960x540 clip to box b, filling a 540x340 tile. */
const Crop: React.FC<{ src: string; b: Box }> = ({ src, b }) => {
  const s = Math.min(540 / b[2], 340 / b[3]) * 0.8;
  return (
    <div style={{ position: "absolute", left: 270 - (b[0] + b[2] / 2) * s, top: 170 - (b[1] + b[3] / 2) * s, width: 960 * s, height: 540 * s }}>
      <Video src={staticFile(src)} muted style={{ width: 960 * s, height: 540 * s }} trimBefore={8 * FPS} />
    </div>
  );
};

const Triptych: React.FC = () => {
  const frame = useCurrentFrame();
  const o = at("h3");
  const sp = wave.span as [number, number];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ display: "flex", gap: 50 }}>
        <Tile at={wordAt("h3", "parcel") - o} label="a parcel label"><Crop src="clips/c1_input.mp4" b={[40, 372, 230, 150]} /></Tile>
        <Tile at={wordAt("h3", "society") - o} label="a society board"><Crop src="clips/c1_input.mp4" b={[620, 40, 320, 70]} /></Tile>
        <Tile at={wordAt("h3", "number") - o} label="a number, spoken">
          <svg width="540" height="340">
            {wave.peaks.map((pk, i) => {
              const t = (i / wave.peaks.length) * wave.duration_s;
              const inSpan = t >= sp[0] && t <= sp[1];
              const h = Math.max(4, pk * 280 * interpolate(frame, [wordAt("h3", "number") - o, wordAt("h3", "number") - o + 20], [0, 1], clamp));
              return <rect key={i} x={20 + i * 2.5} y={170 - h / 2} width={1.6} height={h} fill={inSpan ? C.amber : C.dim} />;
            })}
          </svg>
        </Tile>
      </div>
    </AbsoluteFill>
  );
};

const FixedList: React.FC = () => {
  const o = at("p1");
  const p2 = at("p2") - o;
  const frame = useCurrentFrame();
  const listOut = interpolate(frame, [p2 - 6, p2], [1, 0], clamp);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ opacity: listOut }}>
        <KineticTitle size={70} top={180} words={[{ text: "Most tools look for a fixed list:", at: 0 }]} />
        <KineticTitle size={120} words={["Faces.", "License plates.", "Screens.", "Documents."].map((w) => ({ text: w, at: wordAt("p1", w.split(" ")[0]) - o }))} />
      </AbsoluteFill>
      <Sequence from={p2}>
        <StatCard value="0 / 4" label="planted leaks found by the fixed list · held-out clips" at={0} />
      </Sequence>
    </AbsoluteFill>
  );
};

const VIDEOS: Box = [240, 457, 2080, 623];
const INPUT_PANE: Box = [240, 457, 1028, 623];

export const Main: React.FC = () => {
  const frame = useCurrentFrame(); // absolute frame (Main is the root)
  const sc = (a: string, b: string | null) => ({ from: Math.max(0, at(a)), durationInFrames: (b ? at(b) : T.total) - Math.max(0, at(a)) });
  const S = {
    hook: sc("h1", "h3"), trip: sc("h3", "p1"), list: sc("p1", "a1"), aha: sc("a1", "a3"), scrub: sc("a3", "a4"), stat: sc("a4", "f1"),
    find: sc("f1", "f1b"), checks: sc("f1b", "f2"), mask: sc("f2", "v1"), voice: sc("v1", "r1"), pay: sc("r1", "r2b"), pay2: sc("r2b", "r3"),
    gate: sc("r3", "c0"), term: sc("c0", "c1"), outro: sc("c1", null),
  };
  const allEmph = (T as unknown as { emph: Record<string, Record<string, number>> }).emph;
  const emphasis = Object.values(allEmph).flatMap((o) => Object.keys(o));
  const rel = (f: number, s: { from: number }) => f - s.from;

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Background />
      <Sequence name="Hook" {...S.hook}><Hook /></Sequence>
      <Sequence name="Triptych" {...S.trip}><Triptych /></Sequence>
      <Sequence name="Fixed list" {...S.list}><FixedList /></Sequence>

      <Sequence name="Aha: discovery" {...S.aha}>
        <FlowScene flow="overview" trim={1.0} len={S.aha.durationInFrames}
          zoom={[{ t: 1.0, box: null }, { t: 2.4, box: VIDEOS }, { t: 2.4 + (at("a2") - at("a1")) / FPS, box: INPUT_PANE }]}
          cursor={[{ t: 1.0, x: 1500, y: 1300 }, { t: 2.41, x: 347, y: 1134, click: true }, { t: 3.4, x: 2300, y: 1350 }]}>
          <Sequence from={rel(wordAt("a2", "notification"), S.aha)}>
            <Callout x={1210} y={110} at={0} text="Spark: notification banner" sub="“Displays full personal name Rohan Kulkarni in a Messages notification, identifying the person.”" />
          </Sequence>
          <Sequence from={rel(wordAt("a2", "gold"), S.aha)}>
            <Callout x={1210} y={560} at={0} text="Spark: name overlay label" sub="“Displays surname Kulkarni identifying creator”" />
          </Sequence>
          <Sequence from={rel(at("a2b"), S.aha)}>
            <Chip text="fixed classes: face · plate · screen · document" at={0} x={150} y={14} />
          </Sequence>
        </FlowScene>
      </Sequence>
      <Sequence name="Aha: tracking" {...S.scrub}>
        <FlowScene flow="scrub" trim={1.0} len={S.scrub.durationInFrames} zoom={[{ t: 1.0, box: [240, 457, 2080, 700] }]}
          cursor={[{ t: 1.0, x: 932, y: 1134 }, { t: 1.46, x: 932, y: 1134, click: true }, { t: 5.68, x: 1393, y: 1134 }]}>
          <Chip text="SAM 3.1 masks → covers in the exported file" at={6} x={150} y={14} color={C.amber} />
        </FlowScene>
      </Sequence>
      <Sequence name="Stat 0/4 -> 3/4" {...S.stat}>
        <StatCard value="0 / 4" label="fixed list" next={{ value: "3 / 4", label: "with Muse Spark", at: emph("a4", "three of four") - at("a4") }}
          note={{ text: "missed: the delivery-box label · eval/results/final/heldout_results.md", at: emph("a4", "missed") - at("a4") }} />
      </Sequence>

      <Sequence name="Verify: covers" {...S.find}>
        <FlowScene flow="findings" trim={1.8} len={S.find.durationInFrames} zoom={[{ t: 1.8, box: [240, 200, 2080, 330], pad: 1.05 }]} />
      </Sequence>
      <Sequence name="Verify: checks" {...S.checks}>
        <FlowScene flow="checks" trim={1.6} len={S.checks.durationInFrames} zoom={[{ t: 1.6, box: [240, 83, 2080, 478] }]} />
      </Sequence>
      <Sequence name="Mask check" {...S.mask}>
        <FlowScene flow="maskcheck" trim={1.6} len={S.mask.durationInFrames}
          zoom={[{ t: 1.6, box: [240, 120, 2080, 420] }, { t: 1.6 + (at("f3") - at("f2")) / FPS * 0.9, box: [240, 203, 2080, 107], pad: 1.5 }]}
          cursor={[{ t: 1.6, x: 1900, y: 900 }, { t: 2.9, x: 1280, y: 256 }]}>
          <Sequence from={rel(wordAt("f3", "found"), S.mask)}>
            <Callout x={1180} y={640} at={0} color={C.red} text="Rejected: mask held code" sub="OCR read “def total(items):” — Spark claimed “KULKARNI”. Removed before redaction." />
          </Sequence>
        </FlowScene>
      </Sequence>

      <Sequence name="Voice" {...S.voice}>
        <FlowScene flow="voice" trim={1.2} len={S.voice.durationInFrames}
          zoom={[{ t: 1.2, box: [240, 65, 2080, 650] }, { t: 1.2 + (at("v2") - at("v1")) / FPS * 0.6, box: [240, 65, 2080, 441] }]}>
          <Sequence from={rel(at("v3"), S.voice)}>
            <Callout x={1100} y={150} at={0} color={C.red} text="Gate G4b: still FAIL" sub="Mute window over-covers by 2.85 s (limit 2.5 s). Digits heard: 987765 · 5432100 — spoken: 98765 43210." />
          </Sequence>
        </FlowScene>
      </Sequence>

      <Sequence name="Payoff: statuses" {...S.pay}>
        <FlowScene flow="findings" trim={1.8} len={S.pay.durationInFrames} zoom={[{ t: 1.8, box: [240, 65, 2080, 1360] }]}>
          <Sequence from={rel(wordAt("r1", "never"), S.pay)}>
            <Chip text="never “safe” — COVERED · UNRESOLVED · NOT_CHECKED" at={0} x={150} y={14} color={C.amber} />
          </Sequence>
        </FlowScene>
      </Sequence>
      <Sequence name="Payoff: unresolved" {...S.pay2}>
        <FlowScene flow="findings" trim={6.2} len={S.pay2.durationInFrames}
          zoom={[{ t: 6.2, box: [240, 800, 2080, 240] }, { t: 6.2 + (wordAt("r2b", "eight") - at("r2b")) / FPS * 0.5, box: [240, 150, 2080, 620] }]} />
      </Sequence>

      <Sequence name="Gate" {...S.gate}>
        <GateCard at={0} postAt={wordAt("r3", "every") - at("r3")}
          rows={[
            { g: "G1  discovery", frozen: "PASS  3/4", post: "PASS  3/4" },
            { g: "G2  false flags", frozen: "FAIL  2/3", post: "PASS  1/3 *" },
            { g: "G3  tracking", frozen: "PASS", post: "PASS" },
            { g: "G4a spoken digits", frozen: "PASS", post: "PASS" },
            { g: "G4b mute window", frozen: "FAIL  3.13 s", post: "FAIL  2.85 s" },
          ]} />
        <div style={{ position: "absolute", left: 210, top: 905, fontFamily: mono, fontSize: 26, color: C.dim, opacity: interpolate(frame, [wordAt("r3", "every") + 20, wordAt("r3", "every") + 32], [0, 1], clamp) }}>
          * lifting the 10-concept cap made G2 fail again (gate/postgate2). Sources: gate/GATE_RESULT.md, gate/postgate/GATE_RESULT.md
        </div>
      </Sequence>
      <Sequence name="Terminal" {...S.term}>
        <Terminal at={0} cmd="veil run smoke-001/input.mp4 --run-id live-smoke1"
          lines={[
            { text: "spoken PII: digits=2025550146 4.50-9.50s precision=window" },
            { text: "COVERED   visual  man's face       cover verified in decoded output on all 180 masked frames", color: C.green },
            { text: "COVERED   visual  license plate    cover verified in decoded output on all 180 masked frames", color: C.green },
            { text: "COVERED   audio   spoken number    muted; re-transcription found no digit run", color: C.green },
            { text: "check RAN face_output: face detector fired on 36 input and 0 output sampled frames" },
          ]} />
      </Sequence>
      <Sequence name="Outro" {...S.outro}><Outro /></Sequence>

      <Captions emphasis={emphasis} />
      <Audio src={staticFile("vo.wav")} />
    </AbsoluteFill>
  );
};

const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const o = at("c1");
  const p = (f: number) => ({ opacity: interpolate(frame, [f, f + 12], [0, 1], clamp), translate: `0px ${interpolate(frame, [f, f + 14], [20, 0], { ...clamp, easing: EASE })}px` });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 26 }}>
      <div style={{ fontFamily: mono, fontSize: 40, color: C.dim, ...p(0) }}>Models propose. <span style={{ color: C.amber }}>Code decides.</span></div>
      <div style={{ fontFamily: display, fontWeight: 700, fontSize: 220, color: C.text, lineHeight: 1, ...p(wordAt("c1", "veil") - o) }}>Veil</div>
      <div style={{ display: "flex", gap: 18, ...p(wordAt("c1", "muse") - o) }}>
        {["Muse Spark 1.3", "SAM 3.1", "Muse Voice Transcribe"].map((m) => (
          <div key={m} style={{ fontFamily: mono, fontSize: 32, color: C.amber, border: `1px solid ${C.amber}`, borderRadius: 999, padding: "8px 22px" }}>{m}</div>
        ))}
      </div>
      <div style={{ fontFamily: body, fontSize: 44, fontWeight: 600, color: C.text, marginTop: 16, ...p(wordAt("c1", "muse") - o + 10) }}>github.com/thecodekaizen/veil</div>
      <div style={{ position: "absolute", bottom: 150, width: 1500, textAlign: "center", fontFamily: body, fontSize: 22, lineHeight: 1.4, color: C.dim, ...p(10) }}>
        Street footage: Subhashish Panigrahi (Cuttack) and Fowler&amp;fowler (Delhi), Wikimedia Commons, CC BY-SA 3.0, composited with fictional graphics.
        Voiceover: synthetic clone of the author's own voice (Chatterbox, watermarked). All results from committed run artifacts.
      </div>
    </AbsoluteFill>
  );
};
