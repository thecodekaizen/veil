"use client";

import { useEffect, useRef, useState } from "react";
import { completedActions, repairSequenceOrder, resolveSimulationRecovery, simulateAction, simulateSequence, testRepairedSequence } from "@/lib/simulate";
import { SAMPLE_SKILL, type SkillModel } from "@/lib/skill-model";
import { processToSkill } from "@/lib/process-to-skill";
import { clearReviewedProcess, isSavedProcess, loadReviewedProcess, saveReviewedProcess, type SavedProcess } from "@/lib/skill-storage";
import { interpretWhatIf } from "@/lib/what-if";
import { findRecoveryEvent } from "@/lib/learner-review";
import { taskCheckpoint } from "@/lib/task-checkpoint";
import { ProcedureScene } from "@/lib/procedure-scene";
import { applyRevision, revertRevision, type CandidateRevision } from "@/lib/candidate-revision";

type Mode = "teach" | "do" | "simulate";
const MAX_LEARNER_VIDEO_BYTES = 100 * 1024 * 1024;
type LearnedProcess = SavedProcess;
type LearnerObservation = {
  events: { time_seconds: number; action: string; state_id: string; assessment: "consistent" | "divergent" | "unclear"; object_ids: string[]; evidence: string }[];
  divergences: { time_seconds: number; process_difference: string; object_ids: string[]; evidence: string }[];
  recovery_status: "no_divergence_observed" | "underway" | "recovered" | "unclear";
  uncertainties: string[];
  reference_checks: { transition_id: string; status: "matches_reference" | "possible_mismatch" | "not_shown" | "unclear"; time_seconds: number | null; evidence: string; next_guidance: string }[];
  _run?: { model?: string; usage?: { input_tokens?: number; output_tokens?: number } };
};
function isLearnerObservation(value: unknown): value is LearnerObservation {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  const statuses = new Set(["matches_reference", "possible_mismatch", "not_shown", "unclear"]);
  return Array.isArray(item.events)
    && Array.isArray(item.divergences)
    && Array.isArray(item.uncertainties)
    && Array.isArray(item.reference_checks)
    && ["no_divergence_observed", "underway", "recovered", "unclear"].includes(String(item.recovery_status))
    && item.events.every((event) => typeof event === "object" && event !== null && typeof (event as Record<string, unknown>).time_seconds === "number" && typeof (event as Record<string, unknown>).action === "string")
    && item.divergences.every((divergence) => typeof divergence === "object" && divergence !== null && typeof (divergence as Record<string, unknown>).time_seconds === "number" && typeof (divergence as Record<string, unknown>).process_difference === "string")
    && item.reference_checks.every((check) => typeof check === "object" && check !== null && typeof (check as Record<string, unknown>).transition_id === "string" && statuses.has(String((check as Record<string, unknown>).status)) && ((check as Record<string, unknown>).time_seconds === null || typeof (check as Record<string, unknown>).time_seconds === "number") && typeof (check as Record<string, unknown>).evidence === "string" && typeof (check as Record<string, unknown>).next_guidance === "string");
}
type SnapshotObservation = {
  state_id: string;
  assessment: "consistent" | "possible_divergence" | "unclear";
  object_ids: string[];
  evidence: string;
  uncertainties: string[];
  view_guidance: string;
  _run?: { model?: string; usage?: { input_tokens?: number; output_tokens?: number } };
};
type SnapshotCheck = { checkedAt: string; observation: SnapshotObservation };
type GroundedDetection = { object_id: string; box?: { left: number; top: number; right: number; bottom: number }; mask?: { width: number; height: number; bounds: { left: number; top: number; right: number; bottom: number }; path: string } };
type SamGrounding = { model: string; concept: string; image: { width: number; height: number }; detections: GroundedDetection[]; diagnostics: string[] };
type SimulationOrigin = { state: string[]; actionIds: string[]; source: "skill-start" | "camera-checkpoint"; label: string };

function SamOverlayPreview({ grounding, sourceImage }: { grounding: SamGrounding; sourceImage: string }) {
  return <div className="grounding-result"><div className="eyebrow">{grounding.model.toUpperCase()} · {grounding.detections.length} MATCH{grounding.detections.length === 1 ? "" : "ES"}</div>{grounding.detections.length === 0 ? <p>No matching object was segmented in this frame.</p> : <div className="grounding-preview" style={{ aspectRatio: `${grounding.image.width} / ${grounding.image.height}` }}><img src={sourceImage} alt="The selected workspace frame" /><svg viewBox={`0 0 ${grounding.image.width} ${grounding.image.height}`} role="img" aria-label={`SAM segmentation for ${grounding.concept}`}>{grounding.detections.map((detection, index) => <g key={`${detection.object_id}-${index}`}>{detection.mask && <svg x={detection.mask.bounds.left} y={detection.mask.bounds.top} width={detection.mask.bounds.right - detection.mask.bounds.left} height={detection.mask.bounds.bottom - detection.mask.bounds.top} viewBox={`0 0 ${detection.mask.width} ${detection.mask.height}`} preserveAspectRatio="none"><path d={detection.mask.path} className="grounding-mask" /></svg>}{detection.box && <rect x={detection.box.left} y={detection.box.top} width={detection.box.right - detection.box.left} height={detection.box.bottom - detection.box.top} className="grounding-box" />}</g>)}</svg></div>}{grounding.diagnostics.length > 0 && <small>Some mask records could not be parsed: {grounding.diagnostics.join(", ")}</small>}</div>;
}

function SkillTransitionMap({ state, model, activeActionId }: { state: string[]; model: SkillModel; activeActionId?: string }) {
  const stateNames = (model.states ?? []).filter((item) => state.includes(item.id));
  const nextActionId = model.actions.find((action) => !action.produces.every((condition) => state.includes(condition)))?.id;
  const labelFor = (id?: string) => model.states?.find((item) => item.id === id)?.label ?? id?.replaceAll("_", " ") ?? "State not specified";
  const learned = model.status === "learned-from-demonstration";
  return <div className="learned-state-view skill-map-view">
    <div className="eyebrow">CURRENT SIMULATED STATE</div>
    <div className="learned-state-current" aria-live="polite">
      {stateNames.length ? stateNames.map((item) => <div className="learned-state-chip" key={item.id}><span>◉</span>{item.label}</div>) : <div className="learned-state-chip muted">{state.length ? state.map(labelFor).join(" · ") : "No matching state in this model"}</div>}
    </div>
    {stateNames.some((item) => item.observableFacts?.length) && <div className="simulated-state-facts"><strong>Expected appearance in this simulation</strong><ul>{stateNames.flatMap((item) => (item.observableFacts ?? []).map((fact, index) => <li key={`${item.id}-fact-${index}`}>{fact}</li>))}</ul><small>These are model claims to inspect, not observations from your camera.</small></div>}
    <div className="skill-state-map" aria-label="Skill Model transition map">
      <div className="skill-state-map-heading"><span>{learned ? "OBSERVED STEP ORDER" : "SAMPLE STEP ORDER"}</span><span>{model.actions.length} steps</span></div>
      {model.actions.map((action, index) => {
        const complete = action.produces.every((condition) => state.includes(condition));
        const involvedParts = action.objectIds.map((objectId) => model.objects.find((object) => object.id === objectId)?.name).filter((name): name is string => Boolean(name));
        const current = action.id === activeActionId || (!activeActionId && action.id === nextActionId);
        const status = complete ? "complete" : current ? "current" : "pending";
        return <div className={`skill-transition ${status}`} key={action.id} aria-current={current ? "step" : undefined}>
          <div className="skill-transition-marker"><span>{complete ? "✓" : String(index + 1).padStart(2, "0")}</span></div>
          <div className="skill-transition-copy">
            <div className="skill-transition-title"><strong>{action.label}</strong><small>{complete ? "APPLIED IN MODEL" : current ? "NEXT STEP" : "UPCOMING"}</small></div>
            <div className="skill-transition-states"><span>{labelFor(action.fromState ?? (index === 0 ? model.initialState.find((item) => !item.endsWith("_available")) ?? model.initialState[0] : model.actions[index - 1]?.toState ?? model.actions[index - 1]?.produces[0]))}</span><i>→</i><span>{labelFor(action.toState ?? action.produces[0])}</span></div>
            {involvedParts.length > 0 && <small className="skill-transition-parts">PARTS · {involvedParts.join(" + ")}</small>}
            {action.evidence?.[0] && <small className="skill-transition-evidence">Evidence · {action.evidence[0].startSeconds.toFixed(1)}s — {action.evidence[0].observation}</small>}
          </div>
        </div>;
      })}
    </div>
    <p>{learned ? "Steps come from the demonstration you reviewed. This previews the process; it does not simulate physical forces or geometry." : "Sample only. This previews step order; it does not simulate physical forces or geometry."}</p>
  </div>;
}

function AssemblyView({ state, model, activeActionId, blockedActionId }: { state: string[]; model: SkillModel; activeActionId?: string; blockedActionId?: string }) {
  if (model.status === "learned-from-demonstration") {
    return (
      <>
        <ProcedureScene model={model} state={state} activeActionId={activeActionId} />
        <SkillTransitionMap state={state} model={model} activeActionId={activeActionId} />
      </>
    );
  }
  const washer = state.includes("washer_seated");
  const blockedBracketAttempt = blockedActionId === "place-bracket" && !state.includes("bracket_mounted");
  const bracket = state.includes("bracket_mounted") || blockedBracketAttempt;
  const bolt = state.includes("fastener_inserted");
  return (
    <>
      <div className={`assembly-scene ${blockedBracketAttempt ? "attempt-blocked" : ""}`} aria-label={blockedBracketAttempt ? "Illustrative blocked bracket placement preview; the simulated state remains unchanged" : "Illustrative assembly state"}>
        <div className="scene-glow" />
        <div className="part-label label-bracket">SUPPORT BRACKET</div>
        <div className="part-label label-washer">SPACER RING</div>
        <div className="part-label label-base">MOUNTING BASE</div>
        <div className="assembly">
          {bolt && <div className="bolt-part"><span /></div>}
          {bracket && <div className={`bracket-part ${blockedBracketAttempt ? "attempted" : ""}`}><span /></div>}
          {washer && <div className="washer-part"><span /></div>}
          <div className="base-part"><span /></div>
        </div>
        {blockedBracketAttempt && <div className="attempt-blocked-note" role="status"><strong>BLOCKED ATTEMPT · NOT APPLIED</strong><span>Bracket shown in the proposed position; the simulator state remains unchanged because the spacer is not seated.</span></div>}
        <div className="scene-caption">MODELED STEPS · NOT A PHYSICS SIMULATION</div>
      </div>
      <SkillTransitionMap state={state} model={model} activeActionId={activeActionId} />
    </>
  );
}

function VideoPreview({ src, videoRef }: { src: string; videoRef?: React.RefObject<HTMLVideoElement | null> }) {
  return <video ref={videoRef} className="video-preview" src={src} controls playsInline />;
}

export default function Home() {
  const [mode, setMode] = useState<Mode>("teach");
  const [model, setModel] = useState<SkillModel>(SAMPLE_SKILL);
  const [state, setState] = useState<string[]>(model.initialState);
  const [result, setResult] = useState<ReturnType<typeof simulateAction> | null>(null);
  const [sequenceDraft, setSequenceDraft] = useState<string[]>(model.actions.map((action) => action.id));
  const [sequenceResult, setSequenceResult] = useState<ReturnType<typeof simulateSequence> | null>(null);
  const [sequenceCursor, setSequenceCursor] = useState(-1);
  const [sequencePlaying, setSequencePlaying] = useState(false);
  const [simulationOrigin, setSimulationOrigin] = useState<SimulationOrigin>({ state: SAMPLE_SKILL.initialState, actionIds: SAMPLE_SKILL.actions.map((action) => action.id), source: "skill-start", label: "Skill start" });
  const [whatIfPrompt, setWhatIfPrompt] = useState("");
  const [whatIfMessage, setWhatIfMessage] = useState("");
  const [whatIfProposal, setWhatIfProposal] = useState<Extract<ReturnType<typeof interpretWhatIf>, { ok: true }> | null>(null);
  const [mediaUrl, setMediaUrl] = useState("");
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [referencePdf, setReferencePdf] = useState<File | null>(null);
  const [importError, setImportError] = useState("");
  const [observationImportError, setObservationImportError] = useState("");
  const [demoCameraOn, setDemoCameraOn] = useState(false);
  const [recordingDemo, setRecordingDemo] = useState(false);
  const [demoCaptureError, setDemoCaptureError] = useState("");
  const [cameraOn, setCameraOn] = useState(false);
  const [recordingAttempt, setRecordingAttempt] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [narration, setNarration] = useState("");
  const [learnedProcess, setLearnedProcess] = useState<LearnedProcess | null>(null);
  const [activeProcess, setActiveProcess] = useState<LearnedProcess | null>(null);
  const [candidateReviewed, setCandidateReviewed] = useState(false);
  const [storageReady, setStorageReady] = useState(false);
  const [learnError, setLearnError] = useState("");
  const [learning, setLearning] = useState(false);
  const [learnerFile, setLearnerFile] = useState<File | null>(null);
  const [learnerUrl, setLearnerUrl] = useState("");
  const [observation, setObservation] = useState<LearnerObservation | null>(null);
  const [snapshotObservation, setSnapshotObservation] = useState<SnapshotObservation | null>(null);
  const [snapshotFrame, setSnapshotFrame] = useState<{ blob: Blob; dataUrl: string; width: number; height: number } | null>(null);
  const [grounding, setGrounding] = useState<SamGrounding | null>(null);
  const [groundingObjectId, setGroundingObjectId] = useState("");
  const [groundingError, setGroundingError] = useState("");
  const [groundingBusy, setGroundingBusy] = useState(false);
  const [learnerGrounding, setLearnerGrounding] = useState<{ result: SamGrounding; dataUrl: string; seconds: number; objectId: string } | null>(null);
  const [learnerGroundingError, setLearnerGroundingError] = useState("");
  const [learnerGroundingBusy, setLearnerGroundingBusy] = useState(false);
  const [snapshotHistory, setSnapshotHistory] = useState<SnapshotCheck[]>([]);
  const [snapshotError, setSnapshotError] = useState("");
  const [checkingSnapshot, setCheckingSnapshot] = useState(false);
  const [observeError, setObserveError] = useState("");
  const [observing, setObserving] = useState(false);
  const [observeReferencePdf, setObserveReferencePdf] = useState<File | null>(null);
  const [repairedFeedback, setRepairedFeedback] = useState<string | null>(null);
  const [candidateRevisions, setCandidateRevisions] = useState<CandidateRevision[]>([]);
  const [editingTarget, setEditingTarget] = useState<{ type: "object" | "action"; id: string } | null>(null);
  const [editInputDraft, setEditInputDraft] = useState("");
  const observeReferenceInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const referenceInput = useRef<HTMLInputElement>(null);
  const processInput = useRef<HTMLInputElement>(null);
  const observationInput = useRef<HTMLInputElement>(null);
  const demoPlayerRef = useRef<HTMLVideoElement>(null);
  const demoVideoRef = useRef<HTMLVideoElement>(null);
  const demoStreamRef = useRef<MediaStream | null>(null);
  const demoRecorderRef = useRef<MediaRecorder | null>(null);
  const demoChunksRef = useRef<Blob[]>([]);
  const attemptRecorderRef = useRef<MediaRecorder | null>(null);
  const attemptChunksRef = useRef<Blob[]>([]);
  const learnerInput = useRef<HTMLInputElement>(null);
  const learnerVideoRef = useRef<HTMLVideoElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    const saved = loadReviewedProcess();
    if (saved) {
      const restoredModel = processToSkill(saved);
      setLearnedProcess(saved);
      setActiveProcess(saved);
      setModel(restoredModel);
      setState(restoredModel.initialState);
      setSequenceDraft(restoredModel.actions.map((action) => action.id));
      setSimulationOrigin({ state: restoredModel.initialState, actionIds: restoredModel.actions.map((action) => action.id), source: "skill-start", label: "Skill start" });
      setCandidateReviewed(true);
      setMode("do");
    }
    setStorageReady(true);
  }, []);

  useEffect(() => {
    if (storageReady && activeProcess) saveReviewedProcess(activeProcess);
  }, [activeProcess, storageReady]);

  useEffect(() => {
    if (!sequencePlaying || !sequenceResult) return;
    const timer = window.setTimeout(() => {
      const nextCursor = sequenceCursor + 1;
      const step = sequenceResult.steps[nextCursor];
      if (!step) {
        setSequencePlaying(false);
        return;
      }
      setSequenceCursor(nextCursor);
      setState(step.result.state);
      setResult(step.result);
      if (nextCursor === sequenceResult.steps.length - 1) setSequencePlaying(false);
    }, 850);
    return () => window.clearTimeout(timer);
  }, [sequencePlaying, sequenceCursor, sequenceResult]);

  useEffect(() => () => {
    if (mediaUrl.startsWith("blob:")) URL.revokeObjectURL(mediaUrl);
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, [mediaUrl]);

  useEffect(() => () => {
    if (learnerUrl.startsWith("blob:")) URL.revokeObjectURL(learnerUrl);
  }, [learnerUrl]);

  useEffect(() => {
    if (demoCameraOn && demoVideoRef.current && demoStreamRef.current) {
      demoVideoRef.current.srcObject = demoStreamRef.current;
    }
  }, [demoCameraOn]);

  useEffect(() => () => {
    if (demoRecorderRef.current?.state === "recording") demoRecorderRef.current.stop();
    if (attemptRecorderRef.current?.state === "recording") attemptRecorderRef.current.stop();
    demoStreamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  useEffect(() => () => {
    if (mode === "teach") {
      if (demoRecorderRef.current?.state === "recording") demoRecorderRef.current.stop();
      demoStreamRef.current?.getTracks().forEach((track) => track.stop());
      demoStreamRef.current = null;
      setDemoCameraOn(false);
      setRecordingDemo(false);
    }
    if (mode === "do") {
      if (attemptRecorderRef.current?.state === "recording") attemptRecorderRef.current.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setCameraOn(false);
      setRecordingAttempt(false);
    }
  }, [mode]);

  useEffect(() => {
    if (cameraOn && videoRef.current && streamRef.current) videoRef.current.srcObject = streamRef.current;
  }, [cameraOn]);

  function resetSimulation() {
    setSequencePlaying(false);
    setState(simulationOrigin.state);
    setResult(null);
    setSequenceDraft(simulationOrigin.actionIds);
    setSequenceResult(null);
    setSequenceCursor(-1);
    setWhatIfProposal(null);
    setWhatIfMessage("");
  }

  /** Return to the Do surface after a simulation detour. Clears simulation
   *  playback but keeps snapshot history, observations and the reviewed model.
   *  The camera stream is stopped by the mode-change cleanup effect — provide
   *  a clear restart action instead of pretending it survived. */
  function returnToTask() {
    setSequencePlaying(false);
    setSequenceResult(null);
    setSequenceCursor(-1);
    setResult(null);
    setWhatIfProposal(null);
    setWhatIfMessage("");
    // Restore simulation origin to skill-start so re-entering Simulate later
    // begins from the full model, not a stale camera checkpoint.
    const fullOrigin: SimulationOrigin = {
      state: model.initialState,
      actionIds: model.actions.map((action) => action.id),
      source: "skill-start",
      label: "Skill start",
    };
    setSimulationOrigin(fullOrigin);
    setState(fullOrigin.state);
    setSequenceDraft(fullOrigin.actionIds);
    setMode("do");
  }

  function moveSequenceAction(index: number, offset: -1 | 1) {
    const target = index + offset;
    if (target < 0 || target >= sequenceDraft.length) return;
    setSequencePlaying(false);
    setSequenceDraft((current) => {
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
    setSequenceResult(null);
    setSequenceCursor(-1);
    setResult(null);
    setWhatIfProposal(null);
    setWhatIfMessage("");
  }

  function runSequenceWhatIf() {
    setSequencePlaying(false);
    const next = simulateSequence(model, sequenceDraft, simulationOrigin.state);
    setSequenceResult(next);
    const firstStep = next.steps[0];
    setSequenceCursor(firstStep ? 0 : -1);
    setState(firstStep?.result.state ?? next.initialState);
    setResult(firstStep?.result ?? null);
  }

  function previewNaturalWhatIf() {
    const interpretation = interpretWhatIf(model, sequenceDraft, whatIfPrompt);
    if (!interpretation.ok) {
      setWhatIfProposal(null);
      setWhatIfMessage(interpretation.message);
      return;
    }
    setWhatIfProposal(interpretation);
    setWhatIfMessage("");
  }

  function applyNaturalWhatIf() {
    if (!whatIfProposal) return;
    setSequencePlaying(false);
    setSequenceDraft(whatIfProposal.actionIds);
    setSequenceResult(null);
    setSequenceCursor(-1);
    setResult(null);
    setState(simulationOrigin.state);
    setWhatIfProposal(null);
    setWhatIfMessage("Proposed order added below. Review it, then run the simulation.");
  }

  function moveSimulationCursor(offset: -1 | 1) {
    if (!sequenceResult) return;
    setSequencePlaying(false);
    const nextCursor = Math.max(0, Math.min(sequenceResult.steps.length - 1, sequenceCursor + offset));
    const step = sequenceResult.steps[nextCursor];
    if (!step) return;
    setSequenceCursor(nextCursor);
    setState(step.result.state);
    setResult(step.result);
  }

  function toggleSequencePlayback() {
    if (!sequenceResult?.steps.length) return;
    if (sequencePlaying) {
      setSequencePlaying(false);
      return;
    }
    if (sequenceCursor >= sequenceResult.steps.length - 1) {
      const firstStep = sequenceResult.steps[0];
      if (!firstStep) return;
      setSequenceCursor(0);
      setState(firstStep.result.state);
      setResult(firstStep.result);
    }
    setSequencePlaying(sequenceResult.steps.length > 1);
  }

  async function startCamera() {
    setCameraError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("Camera access is unavailable here. Open SHOWME on localhost or HTTPS.");
      return;
    }
    try {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      setCameraOn(true);
    } catch {
      setCameraError("Camera permission was not granted. You can still inspect the sample procedure.");
    }
  }

  function stopCamera() {
    if (attemptRecorderRef.current?.state === "recording") {
      attemptRecorderRef.current.stop();
      return;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setCameraOn(false);
  }

  async function startAttemptRecording() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setCameraError("Camera recording is unavailable here. You can upload a learner clip instead.");
      return;
    }
    try {
      let stream = streamRef.current;
      if (!stream) {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
        streamRef.current = stream;
        setCameraOn(true);
      }
      const mimeType = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/mp4"]
        .find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      attemptChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) attemptChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(attemptChunksRef.current, { type: recorder.mimeType || "video/webm" });
        const extension = blob.type.includes("mp4") ? "mp4" : "webm";
        if (blob.size > 0) chooseLearnerVideo(new File([blob], `showme-attempt.${extension}`, { type: blob.type }));
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        attemptRecorderRef.current = null;
        setRecordingAttempt(false);
        setCameraOn(false);
      };
      attemptRecorderRef.current = recorder;
      recorder.start(1000);
      setRecordingAttempt(true);
      setCameraError("");
    } catch {
      setCameraError("The browser could not start recording. You can upload a learner clip instead.");
    }
  }

  function loadReviewedCandidate() {
    if (!learnedProcess) return;
    const nextModel = processToSkill(learnedProcess);
    setActiveProcess(learnedProcess);
    setModel(nextModel);
    setState(nextModel.initialState);
    setSequenceDraft(nextModel.actions.map((action) => action.id));
    setSimulationOrigin({ state: nextModel.initialState, actionIds: nextModel.actions.map((action) => action.id), source: "skill-start", label: "Skill start" });
    setSequenceResult(null);
    setSequenceCursor(-1);
    setResult(null);
    setWhatIfProposal(null);
    setWhatIfMessage("");
    setSnapshotObservation(null);
    setSnapshotFrame(null);
    setGrounding(null);
    setGroundingError("");
    setSnapshotHistory([]);
    setMode("do");
  }

  async function importSavedProcess(file: File | null) {
    if (!file) return;
    try {
      const parsed: unknown = JSON.parse(await file.text());
      const candidate = typeof parsed === "object" && parsed !== null && "process" in parsed
        ? (parsed as { process: unknown }).process
        : parsed;
      if (!isSavedProcess(candidate)) throw new Error("This file is not a valid SHOWME process model.");
      setLearnedProcess(candidate);
      setCandidateRevisions([]);
      setEditingTarget(null);
      setCandidateReviewed(false);
      setImportError("");
      setLearnError("");
    } catch (error) {
      setImportError(error instanceof Error ? error.message : "SHOWME could not read this process model.");
    } finally {
      if (processInput.current) processInput.current.value = "";
    }
  }

  async function importSavedObservation(file: File | null) {
    if (!file) return;
    try {
      if (!activeProcess) throw new Error("Load and review the matching process model first.");
      const parsed: unknown = JSON.parse(await file.text());
      const candidate = typeof parsed === "object" && parsed !== null && "observation" in parsed
        ? (parsed as { observation: unknown }).observation
        : parsed;
      if (!isLearnerObservation(candidate)) throw new Error("This file is not a valid SHOWME learner review.");
      const expectedIds = activeProcess.transitions.filter((transition) => transition.reference_evidence?.length).map((transition) => transition.id).sort();
      const actualIds = candidate.reference_checks.map((check) => check.transition_id).sort();
      if (JSON.stringify(expectedIds) !== JSON.stringify(actualIds)) throw new Error("This review belongs to a different process model.");
      setObservation(candidate);
      setObservationImportError("");
      setObserveError("");
    } catch (error) {
      setObservationImportError(error instanceof Error ? error.message : "SHOWME could not read this learner review.");
    } finally {
      if (observationInput.current) observationInput.current.value = "";
    }
  }

  function mapConfirmedConstraint(transitionId: string, constraintIndex: number, requiredState: string) {
    setLearnedProcess((current) => {
      if (!current) return current;
      const remaining = (current.human_confirmed_constraints ?? []).filter((item) => !(item.transition_id === transitionId && (item.candidate_constraint_index ?? item.precondition_index) === constraintIndex));
      return {
        ...current,
        human_confirmed_constraints: requiredState
          ? [...remaining, { transition_id: transitionId, candidate_constraint_index: constraintIndex, required_state: requiredState }]
          : remaining,
      };
    });
  }

  function forgetReviewedSkill() {
    clearReviewedProcess();
    setActiveProcess(null);
    setLearnedProcess(null);
    setCandidateRevisions([]);
    setEditingTarget(null);
    setCandidateReviewed(false);
    setModel(SAMPLE_SKILL);
    setState(SAMPLE_SKILL.initialState);
    setSequenceDraft(SAMPLE_SKILL.actions.map((action) => action.id));
    setSimulationOrigin({ state: SAMPLE_SKILL.initialState, actionIds: SAMPLE_SKILL.actions.map((action) => action.id), source: "skill-start", label: "Skill start" });
    setSequenceResult(null);
    setSequenceCursor(-1);
    setResult(null);
    setWhatIfPrompt("");
    setWhatIfProposal(null);
    setWhatIfMessage("");
    setObservation(null);
    setSnapshotObservation(null);
    setSnapshotFrame(null);
    setGrounding(null);
    setGroundingError("");
    setSnapshotHistory([]);
    setLearnerFile(null);
    setLearnerUrl((previous) => {
      if (previous.startsWith("blob:")) URL.revokeObjectURL(previous);
      return "";
    });
    setMode("teach");
  }

  function chooseLearnerVideo(file?: File) {
    if (!file) return;
    if (file.size > MAX_LEARNER_VIDEO_BYTES) {
      setLearnerFile(null);
      setLearnerUrl((previous) => {
        if (previous.startsWith("blob:")) URL.revokeObjectURL(previous);
        return "";
      });
      setObservation(null);
      setObserveError("This video is over 100 MB. Choose a compressed copy to analyze it; the original stays on your device.");
      if (learnerInput.current) learnerInput.current.value = "";
      return;
    }
    setLearnerFile(file);
    setLearnerUrl((previous) => {
      if (previous.startsWith("blob:")) URL.revokeObjectURL(previous);
      return URL.createObjectURL(file);
    });
    setObservation(null);
    setLearnerGrounding(null);
    setLearnerGroundingError("");
    setObserveError("");
  }

  function saveLearnerReview() {
    if (!observation || !activeProcess) return;
    const review = {
      format: "showme-learner-review-v1",
      saved_at: new Date().toISOString(),
      source: { filename: learnerFile?.name ?? null, duration_seconds: learnerVideoRef.current?.duration || null },
      process: activeProcess,
      observation,
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(review, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "showme-learner-review.json";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function observeLearnerVideo() {
    if (!activeProcess || !learnerFile) return;
    setObserving(true);
    setObservation(null);
    setLearnerGrounding(null);
    setLearnerGroundingError("");
    setObserveError("");
    const form = new FormData();
    form.set("video", learnerFile);
    form.set("process_json", JSON.stringify(activeProcess));
    if (observeReferencePdf) {
      form.set("reference_pdf", observeReferencePdf);
    }
    try {
      const api = process.env.NEXT_PUBLIC_SHOWME_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${api}/api/skills/observe`, { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "SHOWME could not observe this learner video.");
      setObservation(payload.observation as LearnerObservation);
    } catch (error) {
      setObserveError(error instanceof Error ? error.message : "SHOWME could not reach the local observation service.");
    } finally {
      setObserving(false);
    }
  }

  async function checkCurrentState() {
    const video = videoRef.current;
    if (!activeProcess || !video || video.videoWidth === 0 || video.videoHeight === 0) {
      setSnapshotError("Start the camera and wait for the workspace image before checking.");
      return;
    }
    setCheckingSnapshot(true);
    setSnapshotError("");
    setSnapshotObservation(null);
    setSnapshotFrame(null);
    setGrounding(null);
    setGroundingError("");
    const checkedAt = new Date().toISOString();
    try {
      const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
      canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Could not capture the current camera frame.");
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const image = await new Promise<Blob>((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Could not encode the camera frame.")), "image/jpeg", 0.82));
      const form = new FormData();
      form.set("image", image, "snapshot.jpg");
      form.set("process_json", JSON.stringify(activeProcess));
      const api = process.env.NEXT_PUBLIC_SHOWME_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${api}/api/skills/observe-snapshot`, { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "SHOWME could not inspect this camera frame.");
      const nextObservation = payload.observation as SnapshotObservation;
      setSnapshotFrame({ blob: image, dataUrl: canvas.toDataURL("image/jpeg", 0.82), width: canvas.width, height: canvas.height });
      setGrounding(null);
      setGroundingError("");
      setGroundingObjectId(nextObservation.object_ids.find((id) => id !== "unknown" && activeProcess.objects.some((object) => object.id === id)) ?? "");
      setSnapshotObservation(nextObservation);
      setSnapshotHistory((history) => [...history, { checkedAt, observation: nextObservation }].slice(-12));
    } catch (error) {
      setSnapshotError(error instanceof Error ? error.message : "SHOWME could not reach the local snapshot service.");
    } finally {
      setCheckingSnapshot(false);
    }
  }

  async function groundSnapshotObject() {
    if (!activeProcess || !snapshotFrame || !groundingObjectId) return;
    const object = activeProcess.objects.find((item) => item.id === groundingObjectId);
    if (!object) return;
    setGroundingBusy(true);
    setGroundingError("");
    setGrounding(null);
    try {
      setGrounding(await requestObjectGrounding(snapshotFrame, object.id));
    } catch (error) {
      setGroundingError(error instanceof Error ? error.message : "SHOWME could not reach the SAM grounding service.");
    } finally {
      setGroundingBusy(false);
    }
  }

  async function requestObjectGrounding(frame: { blob: Blob; width: number; height: number }, objectId: string) {
    if (!activeProcess) throw new Error("Load a reviewed Skill Model first.");
    const form = new FormData();
    form.set("image", frame.blob, "snapshot.jpg");
    form.set("process_json", JSON.stringify(activeProcess));
    form.set("object_id", objectId);
    form.set("image_width", String(frame.width));
    form.set("image_height", String(frame.height));
    const api = process.env.NEXT_PUBLIC_SHOWME_API_URL ?? "http://localhost:8000";
    const response = await fetch(`${api}/api/skills/ground-object`, { method: "POST", body: form });
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "SAM could not locate this object in the selected frame.");
    return payload as SamGrounding;
  }

  async function groundLearnerEvidence(seconds: number, objectId: string) {
    const video = learnerVideoRef.current;
    if (!video || !activeProcess || !activeProcess.objects.some((object) => object.id === objectId)) return;
    setLearnerGroundingBusy(true);
    setLearnerGroundingError("");
    setLearnerGrounding(null);
    try {
      video.pause();
      const target = Math.max(0, Math.min(seconds, Number.isFinite(video.duration) ? video.duration : seconds));
      if (Math.abs(video.currentTime - target) > 0.04) {
        await new Promise<void>((resolve, reject) => {
          const timeout = window.setTimeout(() => finish(new Error("The learner video did not seek to the evidence timestamp.")), 5000);
          const finish = (error?: Error) => {
            window.clearTimeout(timeout);
            video.removeEventListener("seeked", onSeeked);
            error ? reject(error) : resolve();
          };
          const onSeeked = () => finish();
          video.addEventListener("seeked", onSeeked, { once: true });
          video.currentTime = target;
        });
      }
      if (!video.videoWidth || !video.videoHeight) throw new Error("The selected learner frame is not ready yet.");
      const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
      canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Could not capture the learner video frame.");
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((frame) => frame ? resolve(frame) : reject(new Error("Could not encode the learner frame.")), "image/jpeg", 0.82));
      const dataUrl = canvas.toDataURL("image/jpeg", 0.82);
      const result = await requestObjectGrounding({ blob, width: canvas.width, height: canvas.height }, objectId);
      setLearnerGrounding({ result, dataUrl, seconds: target, objectId });
    } catch (error) {
      setLearnerGroundingError(error instanceof Error ? error.message : "SHOWME could not ground this learner frame.");
    } finally {
      setLearnerGroundingBusy(false);
    }
  }

  function inspectLearnerEvidence(seconds: number) {
    const video = learnerVideoRef.current;
    if (!video) return;
    video.currentTime = Math.max(0, Math.min(seconds, Number.isFinite(video.duration) ? video.duration : seconds));
    void video.play().catch(() => undefined);
  }

  function objectLabels(ids: string[]) {
    if (ids.length === 0) return "No specific object grounded";
    return ids.map((id) => activeProcess?.objects.find((object) => object.id === id)?.label ?? id.replaceAll("_", " ")).join(" · ");
  }

  function chooseVideo(file?: File) {
    if (!file) return;
    setSourceFile(file);
    setMediaUrl((previous) => {
      if (previous.startsWith("blob:")) URL.revokeObjectURL(previous);
      return URL.createObjectURL(file);
    });
    setLearnedProcess(null);
    setCandidateRevisions([]);
    setEditingTarget(null);
    setLearnError("");
  }

  async function startDemoCamera() {
    setDemoCaptureError("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setDemoCaptureError("Camera recording is unavailable here. Use a supported browser on localhost or HTTPS, or upload a video.");
      return;
    }
    try {
      demoStreamRef.current?.getTracks().forEach((track) => track.stop());
      demoStreamRef.current = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      setDemoCameraOn(true);
    } catch {
      setDemoCaptureError("Camera permission was not granted. You can still upload a demonstration video.");
    }
  }

  function stopDemoCamera() {
    if (demoRecorderRef.current?.state === "recording") {
      demoRecorderRef.current.stop();
      return;
    }
    demoStreamRef.current?.getTracks().forEach((track) => track.stop());
    demoStreamRef.current = null;
    setDemoCameraOn(false);
  }

  function startDemoRecording() {
    const stream = demoStreamRef.current;
    if (!stream) return;
    try {
      const mimeType = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/mp4"]
        .find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      demoChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) demoChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(demoChunksRef.current, { type: recorder.mimeType || "video/webm" });
        const extension = blob.type.includes("mp4") ? "mp4" : "webm";
        if (blob.size > 0) chooseVideo(new File([blob], `showme-demonstration.${extension}`, { type: blob.type }));
        demoStreamRef.current?.getTracks().forEach((track) => track.stop());
        demoStreamRef.current = null;
        demoRecorderRef.current = null;
        setRecordingDemo(false);
        setDemoCameraOn(false);
      };
      demoRecorderRef.current = recorder;
      recorder.start(1000);
      setRecordingDemo(true);
      setDemoCaptureError("");
    } catch {
      setDemoCaptureError("The browser could not start recording. Try uploading a video instead.");
    }
  }

  async function learnFromVideo() {
    if (!sourceFile) return;
    setLearning(true);
    setLearnError("");
    setLearnedProcess(null);
    setCandidateRevisions([]);
    setEditingTarget(null);
    const form = new FormData();
    form.set("video", sourceFile);
    form.set("narration", narration);
    if (referencePdf) form.set("reference_pdf", referencePdf);
    try {
      const api = process.env.NEXT_PUBLIC_SHOWME_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${api}/api/skills/learn`, { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "SHOWME could not learn from this video.");
      setLearnedProcess(payload.process as LearnedProcess);
      setCandidateRevisions([]);
      setEditingTarget(null);
      setCandidateReviewed(false);
    } catch (error) {
      setLearnError(error instanceof Error ? error.message : "SHOWME could not reach the local learning service.");
    } finally {
      setLearning(false);
    }
  }

  function seekDemoVideo(seconds: number) {
    const video = demoPlayerRef.current;
    if (!video) return;
    video.currentTime = Math.max(0, Math.min(seconds, Number.isFinite(video.duration) ? video.duration : seconds));
    void video.play().catch(() => undefined);
  }

  function startCandidateEdit(type: "object" | "action", id: string, currentValue: string) {
    setEditingTarget({ type, id });
    setEditInputDraft(currentValue);
  }

  function cancelCandidateEdit() {
    setEditingTarget(null);
    setEditInputDraft("");
  }

  function commitCandidateEdit() {
    if (!learnedProcess || !editingTarget) return;
    const result = applyRevision(
      learnedProcess,
      candidateRevisions,
      editingTarget.type,
      editingTarget.id,
      editInputDraft,
    );
    if (result.applied) {
      setLearnedProcess(result.process);
      setCandidateRevisions(result.revisions);
    }
    setEditingTarget(null);
    setEditInputDraft("");
  }

  function handleRevertRevision(revisionId: string) {
    if (!learnedProcess) return;
    const result = revertRevision(learnedProcess, candidateRevisions, revisionId);
    if (result.reverted) {
      setLearnedProcess(result.process);
      setCandidateRevisions(result.revisions);
    }
  }

  const checkpoint = taskCheckpoint(model, snapshotHistory, checkingSnapshot || Boolean(snapshotError));
  const nextCheckpointState = model.states?.find((item) => item.id === checkpoint.nextAction?.toState);
  const done = completedActions(model, state);
  const referenceSequence = simulateSequence(model, simulationOrigin.actionIds, simulationOrigin.state);
  const snapshotActionIndex = snapshotObservation?.assessment === "consistent" && snapshotObservation.state_id !== "unknown"
    ? model.actions.reduce((lastIndex, action, index) => action.toState === snapshotObservation.state_id ? index : lastIndex, -1)
    : -1;
  const snapshotCanContinue = Boolean(activeProcess && snapshotObservation?.assessment === "consistent" && snapshotObservation.state_id !== "unknown" && (model.initialState.includes(snapshotObservation.state_id) || (snapshotActionIndex >= 0 && snapshotActionIndex < model.actions.length - 1)));
  const labelState = (stateId: string) => model.states?.find((item) => item.id === stateId)?.label ?? stateId.replaceAll("_", " ");
  const sequenceStatusLabel = (status: ReturnType<typeof simulateSequence>["status"]) => status === "completed" ? "modeled end state reached" : status === "blocked" ? "stops at confirmed requirement" : "transition not observed";

  function startSimulationFromSnapshot() {
    if (!snapshotCanContinue || !snapshotObservation || snapshotObservation.assessment !== "consistent") return;
    setSequencePlaying(false);
    const isInitial = model.initialState.includes(snapshotObservation.state_id);
    const remainingActions = isInitial ? model.actions : model.actions.slice(snapshotActionIndex + 1);
    const origin: SimulationOrigin = {
      state: [snapshotObservation.state_id],
      actionIds: remainingActions.map((action) => action.id),
      source: "camera-checkpoint",
      label: `Frame check · ${labelState(snapshotObservation.state_id)}`,
    };
    setSimulationOrigin(origin);
    setState(origin.state);
    setSequenceDraft(origin.actionIds);
    setSequenceResult(null);
    setSequenceCursor(-1);
    setResult(null);
    setWhatIfProposal(null);
    setWhatIfMessage("");
    setMode("simulate");
  }
  const proposedConstraints = model.actions.flatMap((action) =>
    action.constraints.filter((constraint) => constraint.status === "proposed").map((constraint) => ({ action: action.label, description: constraint.description })),
  );

  const reportedRecoveryEvent = observation?.recovery_status === "recovered"
    ? findRecoveryEvent(observation.events, observation.divergences, activeProcess?.states.map((state) => state.id) ?? [])
    : undefined;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#home" aria-label="SHOWME home"><span className="brand-symbol">s</span><span>SHOWME</span></a>
        <div className="sidebar-label">YOUR WORKSPACE</div>
        <button className={`nav-item ${mode === "teach" ? "selected" : ""}`} onClick={() => setMode("teach")}><span className="nav-icon">◉</span> Teach <span className="nav-step">01</span></button>
        <button className={`nav-item ${mode === "do" ? "selected" : ""}`} onClick={() => setMode("do")}><span className="nav-icon">◎</span> Do <span className="nav-step">02</span></button>
        <button className={`nav-item ${mode === "simulate" ? "selected" : ""}`} onClick={() => setMode("simulate")}><span className="nav-icon">⌁</span> Simulate <span className="nav-step">03</span></button>
        <div className="sidebar-bottom"><span className="local-indicator" /> LOCAL PROTOTYPE</div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div className="breadcrumbs">WORKSPACE <span>/</span> {mode.toUpperCase()}</div>
          <div className="model-status"><span className="status-dot" /> {model.status === "learned-from-demonstration" ? "REVIEWED PROCESS MODEL" : "SAMPLE PROCESS MODEL · NO VIDEO"}</div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">SHOWME · {mode === "teach" ? "1 · BUILD A PROCESS MODEL" : mode === "do" ? "2 · CHECK AN ATTEMPT" : "3 · TEST AN ALTERNATIVE"}</div>
              <h1>{mode === "teach" ? <>Build a model<br /><em>from a demo.</em></> : mode === "do" ? <>Check a learner’s<br /><em>attempt.</em></> : <>Test a different<br /><em>step order.</em></>}</h1>
              <p className="lead">{mode === "teach" ? "Record or upload a task video. SHOWME proposes the objects, steps, states, and evidence for you to review before use." : mode === "do" ? "Check a camera frame or compare a separate recording with the reviewed process model. The camera preview does not track actions continuously." : "Reorder steps and run the proposed sequence against the same process model. Results show modeled states, not physical forces or geometry."}</p>
            </div>
            <div className="product-thesis"><span>ONE PROCESS MODEL</span><p>Teach creates it.<br /><strong>Do checks against it. Simulate tests it.</strong></p></div>
          </div>

          <nav className="mode-tabs" aria-label="SHOWME workflow">
            {(["teach", "do", "simulate"] as const).map((tab, index) => <button key={tab} aria-current={mode === tab ? "step" : undefined} className={mode === tab ? "active" : ""} onClick={() => setMode(tab)}><span>0{index + 1}</span><span className="mode-tab-copy"><strong>{tab[0].toUpperCase() + tab.slice(1)}</strong><small>{tab === "teach" ? "Record and review" : tab === "do" ? "Check an attempt" : "Test an order"}</small></span></button>)}
          </nav>

          {mode === "simulate" && <div className="work-grid">
            <section className="card simulation-card">
              <div className="card-heading"><div><div className="eyebrow">SAME MODEL USED IN TEACH AND DO</div><h2>{model.title}</h2></div><button className="text-action" onClick={resetSimulation}>Reset simulation ↺</button></div>
              <div className="fixture-note"><span>i</span><p>{model.status === "learned-from-demonstration" ? `This model reflects one reviewed demonstration. It does not prove the process is complete or that another order is impossible. Starting point: ${simulationOrigin.label}.` : "Sample only: this process was not built from a demonstration. Use Teach to create a model from your video."}</p></div>
              {simulationOrigin.source === "camera-checkpoint" && <div className="simulation-origin-banner" role="status"><span className="eyebrow">EXPLORING FROM A CAMERA CHECKPOINT</span><p>Starting from: <strong>{simulationOrigin.label}</strong>. Simulation runs in a scratchpad; your frame-check history and observations are preserved.</p><small>The camera stream was released when you entered Simulate. You can restart it after returning.</small><button className="primary-button" onClick={returnToTask}>Return to active task <span>→</span></button></div>}
              <AssemblyView state={state} model={model} activeActionId={sequenceResult?.steps[sequenceCursor]?.result.action.id ?? result?.action.id} blockedActionId={result?.accepted === false && result.kind === "blocked" && model.status === "illustrative-fixture" ? result.action.id : undefined} />
              <div className="state-summary"><div><span className="eyebrow">SIMULATED PROGRESS</span><strong>{done.length === model.actions.length ? "All modeled steps applied" : `${done.length} of ${model.actions.length} modeled steps applied`}</strong></div><span className="state-pip"><i className={result?.accepted === false ? "warning" : ""} /></span></div>
              {result && <div className={`result-callout ${result.accepted ? "success" : result.kind === "unobserved" ? "unobserved" : "blocked"}`} role="status"><span className="result-icon">{result.accepted ? "✓" : result.kind === "unobserved" ? "?" : "!"}</span><div><strong>{result.accepted ? "STEP APPLIED IN MODEL" : result.kind === "unobserved" ? "NOT SHOWN IN DEMONSTRATION" : "REQUIRED STEP NOT DONE"}</strong><p>{result.message}</p>{!result.accepted && <small>{result.kind === "unobserved" ? "To check this order, record another demonstration or confirm the requirement." : <>Still needed: {result.missing.map((item) => item.replaceAll("_", " ")).join(", ")}<br />Requirement source: {result.blockedBy?.map((constraint) => constraint.source === "illustrative-fixture" ? "sample rule" : constraint.source === "human-confirmation" ? "confirmed by you" : constraint.source.replaceAll("-", " ")).join(", ")}</>}<br />Suggested recovery: {result.action.recovery}</small>}</div></div>}
              <div className="what-if"><span className="what-if-mark">?</span><div><strong>Test another step order</strong><p>Reorder the actions and run them from {simulationOrigin.label}. SHOWME stops when a confirmed requirement is unmet or the model has no evidence for a transition.</p></div></div>
              <section className="natural-what-if">
                <label className="eyebrow" htmlFor="what-if-prompt">DESCRIBE THE STEP CHANGE</label>
                <div className="natural-what-if-entry"><input id="what-if-prompt" value={whatIfPrompt} onChange={(event) => { setWhatIfPrompt(event.target.value); setWhatIfProposal(null); setWhatIfMessage(""); }} onKeyDown={(event) => { if (event.key === "Enter") previewNaturalWhatIf(); }} placeholder="Move ‘Mount support bracket’ before ‘Place spacer ring’" /><button className="secondary-button" onClick={previewNaturalWhatIf}>Preview step order</button></div>
                {whatIfMessage && <p className="natural-what-if-message" role="status">{whatIfMessage}</p>}
                {whatIfProposal && <div className="what-if-proposal" aria-live="polite"><strong>{whatIfProposal.summary}</strong><ol>{whatIfProposal.actionIds.map((actionId, index) => { const action = model.actions.find((item) => item.id === actionId); return action ? <li key={`${actionId}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span>{action.label}</li> : null; })}</ol><button className="text-action" onClick={applyNaturalWhatIf}>Use this proposed order →</button></div>}
                <small className="sequence-disclaimer">Review the interpreted order before running the deterministic process simulation.</small>
              </section>
              <div className="sequence-editor"><div className="sequence-editor-heading"><span className="eyebrow">PROPOSED ACTION ORDER</span><span>Move a step to explore an alternative</span></div>{sequenceDraft.map((actionId, index) => {
                const action = model.actions.find((candidate) => candidate.id === actionId);
                if (!action) return null;
                return <div className="sequence-row" key={action.id}><span className="action-number">{String(index + 1).padStart(2, "0")}</span><strong>{action.label}</strong><div className="sequence-movers"><button aria-label={`Move ${action.label} earlier`} disabled={index === 0} onClick={() => moveSequenceAction(index, -1)}>↑</button><button aria-label={`Move ${action.label} later`} disabled={index === sequenceDraft.length - 1} onClick={() => moveSequenceAction(index, 1)}>↓</button></div></div>;
              })}<div className="sequence-controls"><button className="primary-button" onClick={runSequenceWhatIf}>Run proposed order <span>→</span></button><button className="text-action" onClick={resetSimulation}>Restore original order</button></div></div>
              {sequenceResult && <section className={`sequence-report sequence-${sequenceResult.status}`} aria-live="polite">
                <div className="eyebrow">DETERMINISTIC PROCEDURE SIMULATION</div>
                <strong>{sequenceResult.status === "completed" ? "The proposed sequence reaches its modeled end state." : sequenceResult.status === "blocked" ? "The sequence stops at a confirmed requirement." : "The next transition was not observed from this state."}</strong>
                <div className="state-comparison" aria-label="Reference and proposed final model states">
                  {[{ title: model.status === "learned-from-demonstration" ? (simulationOrigin.source === "camera-checkpoint" ? "REMAINING OBSERVED TRACE" : "OBSERVED REFERENCE TRACE") : "ILLUSTRATIVE REFERENCE", result: referenceSequence }, { title: "PROPOSED ALTERNATIVE", result: sequenceResult }].map(({ title, result: comparison }) => <div className="state-comparison-card" key={title}>
                    <div><span>{title}</span><small>{sequenceStatusLabel(comparison.status)}</small></div>
                    <div className="comparison-state-list">{comparison.finalState.length ? comparison.finalState.map((stateId) => <span className="comparison-state" key={stateId}>{labelState(stateId)}</span>) : <span className="comparison-empty">No modeled states remain.</span>}</div>
                  </div>)}
                </div>
                <small className="sequence-disclaimer">The comparison uses the same process model. Its reference shows one observed order; it does not prove that other orders are impossible.</small>
                {sequenceResult.steps.length > 0 && <div className="sequence-playback"><span>STEP {sequenceCursor + 1} OF {sequenceResult.steps.length} · {sequenceResult.steps[sequenceCursor]?.result.action.label}</span><div><button className="secondary-button" disabled={sequencePlaying || sequenceCursor <= 0} onClick={() => moveSimulationCursor(-1)}>← Previous</button><button className="secondary-button" disabled={sequencePlaying || sequenceCursor >= sequenceResult.steps.length - 1} onClick={() => moveSimulationCursor(1)}>Next →</button><button className="secondary-button" disabled={sequenceResult.steps.length < 2} onClick={toggleSequencePlayback}>{sequencePlaying ? "Pause" : sequenceCursor >= sequenceResult.steps.length - 1 ? "Replay" : "Play"} {sequencePlaying ? "Ⅱ" : "▶"}</button></div></div>}
                <ol>{sequenceResult.steps.map(({ index, result: step }) => <li className={sequenceCursor === index ? "current" : ""} key={`${step.action.id}-${index}`}><span>{step.accepted ? "✓" : step.kind === "blocked" ? "!" : "?"}</span><div><b>{step.action.label}</b><small>{step.accepted ? "Applied to the simulated state." : step.message}{!step.accepted && step.kind === "blocked" && ` Missing: ${step.missing.join(", ")}. Basis: ${step.blockedBy.map((item) => item.source.replaceAll("-", " ")).join(", ")}.`}</small></div></li>)}</ol>
                {(() => {
                  const failedStep = sequenceResult.steps.find((s) => !s.result.accepted)?.result;
                  if (!failedStep || failedStep.accepted) return null;
                  const suggestions = resolveSimulationRecovery(model, failedStep, state);
                  return (
                    <div className="simulation-recovery-container" aria-label="Simulation recovery guidance">
                      {repairedFeedback && <div className="repaired-feedback-note" role="status"><span>ℹ</span> {repairedFeedback}</div>}
                      {suggestions.map((suggestion, index) => (
                        <div className={`simulation-recovery-panel ${suggestion.candidates.length > 0 ? "has-candidates" : "no-candidates"}`} key={`${suggestion.missingStateId}-${index}`}>
                          <span className="eyebrow">{suggestion.isUnobservedTransition ? "UNOBSERVED TRANSITION · NOT ESTABLISHED BY MODEL" : "MISSING PREREQUISITE STATE"}</span>
                          <strong>{suggestion.isUnobservedTransition ? `Transition to "${suggestion.missingStateLabel}" not established` : `Requires: ${suggestion.missingStateLabel}`}</strong>
                          <p>{suggestion.explanation}</p>
                          {suggestion.candidates.length > 0 && (
                            <div className="recovery-candidates-list">
                              {suggestion.candidates.map(({ action, canExecuteNow, unmetPrerequisites }) => (
                                <div className={`recovery-candidate-card ${canExecuteNow ? "executable-now" : "has-prereqs"}`} key={action.id}>
                                  <div className="candidate-card-header">
                                    <strong>{action.label}</strong>
                                    <span className={`executable-tag ${canExecuteNow ? "tag-ready" : "tag-pending"}`}>
                                      {canExecuteNow ? "Executable from current state" : `Requires: ${unmetPrerequisites.join(", ")}`}
                                    </span>
                                  </div>
                                  <button
                                    className="primary-button recovery-apply-button"
                                    onClick={() => {
                                      const testRun = testRepairedSequence(model, sequenceDraft, failedStep.action.id, action.id, simulationOrigin.state);
                                      setSequenceDraft(testRun.repairedActionIds);
                                      setSequenceResult(testRun.simulation);
                                      setSequenceCursor(0);
                                      setState(testRun.simulation.steps[0]?.result.state ?? simulationOrigin.state);
                                      setResult(testRun.simulation.steps[0]?.result ?? null);
                                      if (testRun.hasRemainingBlockers) {
                                        setRepairedFeedback(`Prerequisite "${action.label}" inserted. Sequence advanced, but remaining blocker: ${testRun.remainingBlockerMessage}`);
                                      } else {
                                        setRepairedFeedback(`Prerequisite "${action.label}" inserted. Sequence now reaches its modeled end state!`);
                                      }
                                    }}
                                  >
                                    Insert prerequisite: {action.label} <span>→</span>
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}
                          {suggestion.candidates.length === 0 && (
                            <small className="missing-evidence-note">SHOWME does not fabricate physical transitions that were not demonstrated or confirmed. To support this sequence, demonstrate this transition or confirm its prerequisite in Teach.</small>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })()}
                <small className="sequence-disclaimer">This is a procedural state preview, not a physics simulation or a claim about what happened in the camera view.</small>
              </section>}
            </section>
            <aside className="card model-card">
              <div className="eyebrow">PROCESS MODEL</div><h3>Inspect the model</h3><p className="model-copy">{model.status === "learned-from-demonstration" ? "This model is based on one reviewed demonstration. Check each step and its evidence; an observed order alone does not prove a requirement." : "This sample model is illustrative. It was not created from a demonstration and does not validate task understanding."}</p>
              <div className="model-section"><span>OBJECTS</span>{model.objects.map((object) => <div className="model-row" key={object.id}><i className={`object-swatch ${object.color}`} /><span>{object.name}</span><small>{state.some((item) => item.startsWith(object.id) || item.includes(object.id)) ? "IN USE" : "READY"}</small></div>)}</div>
              <div className="model-section"><span>{model.status === "learned-from-demonstration" ? "REVIEWED PROCESS STEPS" : "SAMPLE STEP ORDER"}</span><div className="dependency-flow">{model.actions.map((action, index) => <div className={state.includes(action.toState ?? action.produces[0]) ? "on" : ""} key={action.id}>{action.label}{model.status === "learned-from-demonstration" && <small className="observed-edge">{action.fromState?.replaceAll("_", " ")} → {action.toState?.replaceAll("_", " ")}</small>}{index < model.actions.length - 1 && <b>↓</b>}</div>)}</div>{proposedConstraints.length > 0 && <div className="hypothesis-list"><span>SUGGESTED REQUIREMENTS · NOT ENFORCED</span>{proposedConstraints.map((item, index) => <p key={`${item.action}-${index}`}><b>{item.action}:</b> {item.description}</p>)}</div>}{model.status === "learned-from-demonstration" && <p className="model-copy model-caveat">Observed order alone does not prove a requirement. Suggested requirements stay unconfirmed until a person or reference evidence confirms them.</p>}</div>
              <div className="model-foot"><span className="status-dot" /> {model.status === "learned-from-demonstration" ? "Reviewed process model" : "Sample model · not from a video"}</div>
            </aside>
          </div>}

          {mode === "teach" && <div className="work-grid teach-grid">
            <section className="card capture-card"><div className="card-heading"><div><div className="eyebrow">STEP 01 · PROVIDE A DEMONSTRATION</div><h2>Show it once.</h2></div><span className="capture-icon">↥</span></div>
              {demoCameraOn && <div className="demo-record-stage"><video ref={demoVideoRef} className="camera-feed" autoPlay muted playsInline /><span className={`record-indicator ${recordingDemo ? "recording" : ""}`}><i /> {recordingDemo ? "RECORDING" : "CAMERA READY"}</span></div>}
              {mediaUrl ? <VideoPreview src={mediaUrl} videoRef={demoPlayerRef} /> : !demoCameraOn && <button className="upload-drop" onClick={() => fileInput.current?.click()}><span className="upload-symbol">↥</span><strong>Choose a demonstration video</strong><small>Use a short clip with the parts and key steps in view.</small><span className="outline-button">Choose video</span></button>}
              <input ref={fileInput} type="file" accept="video/mp4,video/quicktime,video/x-m4v,video/webm" hidden onChange={(event) => chooseVideo(event.target.files?.[0])} />
              {mediaUrl && <div className="clip-actions"><a className="text-action" href={mediaUrl} download={sourceFile?.name || "showme-demonstration.webm"}>Save this clip ↓</a><button className="text-action replace-video" onClick={() => fileInput.current?.click()}>Choose a different video</button></div>}
              <div className="demo-record-controls">{!demoCameraOn ? <button className="secondary-button" onClick={() => void startDemoCamera()}>Record a demonstration</button> : <><button className="primary-button" disabled={recordingDemo} onClick={startDemoRecording}>{recordingDemo ? "Recording…" : "Start recording"}<span>●</span></button><button className="secondary-button" onClick={stopDemoCamera}>{recordingDemo ? "Stop and use clip" : "Stop camera"}</button></>}<span className="small-note">Recording stays in this browser tab until you save it or request analysis.</span></div>
              {demoCaptureError && <div className="inline-honesty" role="alert">{demoCaptureError}</div>}
              <div className="reference-upload"><label className="field-label" htmlFor="reference-pdf">ADD TASK INSTRUCTIONS (OPTIONAL)</label><input ref={referenceInput} id="reference-pdf" type="file" accept="application/pdf,.pdf" onChange={(event) => setReferencePdf(event.target.files?.[0] ?? null)} /><small>Use an official manual or checklist when the demonstration may contain mistakes. SHOWME compares the video with the reference; it still needs your review.</small></div>
              <div className="process-import"><input ref={processInput} type="file" accept="application/json,.json" hidden onChange={(event) => void importSavedProcess(event.target.files?.[0] ?? null)} /><button className="text-action" onClick={() => processInput.current?.click()}>Load an existing process model ↓</button><small>Import a saved JSON model for review without running another model analysis.</small></div>
              {importError && <div className="inline-honesty" role="alert">{importError}</div>}
              <label className="field-label" htmlFor="narration">ADD OPTIONAL NARRATION</label><textarea id="narration" value={narration} onChange={(event) => setNarration(event.target.value)} placeholder="For example: ‘The spacer goes under the bracket.’" />
              <div className="capture-actions"><span className="small-note">Analysis sends the clip{referencePdf ? " and instructions PDF" : ""} to Meta and may use API credits.</span><button className="primary-button" disabled={!sourceFile || learning || demoCameraOn} onClick={() => void learnFromVideo()}>{learning ? "Building process model…" : "Build process model"}<span>→</span></button></div>
              {learnError && <div className="inline-honesty" role="alert">{learnError}</div>}
              {learnedProcess && <section className="candidate-review" aria-live="polite"><div className="candidate-heading"><div><div className="eyebrow">PROPOSED MODEL · REVIEW BEFORE USE</div><h3>{learnedProcess.task_summary}</h3></div><span className="candidate-state">{learnedProcess._validation === "passed" ? "FORMAT CHECK PASSED" : "REVIEW NEEDED"}</span></div>
                <p className="candidate-warning">{learnedProcess._run?.reference_filename ? `SHOWME used ${learnedProcess._run.reference_filename} as the task reference and the video as evidence of what happened. ` : "SHOWME proposed these steps from one video. "}Check the evidence and uncertain details before using this model.</p>
                <div className="candidate-columns">
                  <div>
                    <span className="eyebrow">OBJECTS · {learnedProcess.objects.length}</span>
                    {learnedProcess.objects.map((object) => (
                      <div className="candidate-item" key={object.id}>
                        <div className="candidate-item-header">
                          <strong>{object.label}</strong>
                          {editingTarget?.type === "object" && editingTarget.id === object.id ? (
                            <div className="candidate-edit-box">
                              <input
                                type="text"
                                className="candidate-edit-input"
                                value={editInputDraft}
                                onChange={(e) => setEditInputDraft(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") commitCandidateEdit();
                                  if (e.key === "Escape") cancelCandidateEdit();
                                }}
                                autoFocus
                              />
                              <button type="button" className="secondary-button" onClick={commitCandidateEdit}>Save</button>
                              <button type="button" className="text-action" onClick={cancelCandidateEdit}>Cancel</button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              className="edit-badge-button"
                              onClick={() => startCandidateEdit("object", object.id, object.label)}
                              title={`Edit label for ${object.id}`}
                            >
                              ✎ Edit label
                            </button>
                          )}
                        </div>
                        <small>{object.visual_description}</small>
                      </div>
                    ))}
                  </div>
                  <div>
                    <span className="eyebrow">PROCESS STEPS · {learnedProcess.transitions.length}</span>
                    {learnedProcess.transitions.map((transition) => (
                      <div className="candidate-item" key={transition.id}>
                        <div className="candidate-item-header">
                          <strong>{transition.action}</strong>
                          {editingTarget?.type === "action" && editingTarget.id === transition.id ? (
                            <div className="candidate-edit-box">
                              <input
                                type="text"
                                className="candidate-edit-input"
                                value={editInputDraft}
                                onChange={(e) => setEditInputDraft(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") commitCandidateEdit();
                                  if (e.key === "Escape") cancelCandidateEdit();
                                }}
                                autoFocus
                              />
                              <button type="button" className="secondary-button" onClick={commitCandidateEdit}>Save</button>
                              <button type="button" className="text-action" onClick={cancelCandidateEdit}>Cancel</button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              className="edit-badge-button"
                              onClick={() => startCandidateEdit("action", transition.id, transition.action)}
                              title={`Edit step action for ${transition.id}`}
                            >
                              ✎ Edit step
                            </button>
                          )}
                        </div>
                        <div className="evidence-provenance-group">
                          <div className="evidence-badge-list">
                            {transition.evidence.map((evidence, evIdx) => (
                              <button
                                key={`${transition.id}-ev-${evIdx}`}
                                type="button"
                                className="evidence-badge video-evidence-badge"
                                onClick={() => seekDemoVideo(evidence.start_seconds)}
                                title={`Jump demonstration video to ${evidence.start_seconds.toFixed(1)}s`}
                              >
                                <span className="badge-icon">▶</span>
                                <span className="badge-time">{evidence.start_seconds.toFixed(1)}–{evidence.end_seconds.toFixed(1)}s</span>
                                <span className="badge-text">{evidence.observation}</span>
                              </button>
                            ))}
                          </div>
                          {transition.reference_evidence && transition.reference_evidence.length > 0 && (
                            <div className="reference-badge-list">
                              {transition.reference_evidence.map((citation, citIdx) => (
                                <div key={`${transition.id}-ref-${citIdx}`} className="evidence-badge manual-evidence-badge">
                                  <span className="badge-icon">📄</span>
                                  <span className="badge-citation">Manual p. {citation.page}, step {citation.step}</span>
                                  <span className="badge-text">{citation.observation}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                        <details className="candidate-state-facts">
                          <summary>Inspect proposed result</summary>
                          <p>{learnedProcess.states.find((state) => state.id === transition.to_state)?.description ?? "No target state described"}</p>
                          <ul>
                            {Array.from(new Set([...(learnedProcess.states.find((state) => state.id === transition.to_state)?.observable_facts ?? []), ...transition.postconditions])).map((fact, index) => (
                              <li key={`${transition.id}-fact-${index}`}>{fact}</li>
                            ))}
                          </ul>
                          <small>Check these model claims against the step’s video or manual evidence. A format check does not verify the physical relationship.</small>
                        </details>
                        {(transition.candidate_constraints ?? transition.preconditions ?? []).map((constraint, index) => {
                          const mapped = learnedProcess.human_confirmed_constraints?.find((item) => item.transition_id === transition.id && (item.candidate_constraint_index ?? item.precondition_index) === index)?.required_state ?? "";
                          return (
                            <label className="tentative-condition condition-review" key={`${transition.id}-constraint-${index}`}>
                              <span>{mapped ? "Constraint you confirmed" : "Possible constraint · model hypothesis"}: {constraint}</span>
                              <select
                                aria-label={`Choose a state that confirms the possible constraint for ${transition.action}`}
                                value={mapped}
                                onChange={(event) => mapConfirmedConstraint(transition.id, index, event.target.value)}
                              >
                                <option value="">Leave unconfirmed</option>
                                {learnedProcess.states.map((stateOption) => (
                                  <option value={stateOption.id} key={stateOption.id}>{stateOption.description}</option>
                                ))}
                              </select>
                            </label>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="candidate-bottom"><span>{learnedProcess.states.length} states · {learnedProcess.ordering_observations.length} observed ordering notes · {learnedProcess.uncertainties.length} uncertainties</span><span>{learnedProcess._run?.model ?? "Muse Spark"} · {learnedProcess._run?.usage?.input_tokens ?? 0} input tokens</span></div>
                {learnedProcess.uncertainties.length > 0 && <div className="candidate-uncertainties"><strong>Open questions</strong><ul>{learnedProcess.uncertainties.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div>}
                <section className="candidate-revision-trail" aria-label="Reviewer corrections and audit trail">
                  <div className="revision-trail-heading">
                    <div>
                      <span className="eyebrow">AUDITED CORRECTIONS ({candidateRevisions.length})</span>
                      <small>Human modifications recorded prior to model activation</small>
                    </div>
                  </div>
                  {candidateRevisions.length === 0 ? (
                    <p className="revision-empty-note">
                      No manual label edits recorded yet. Model hypotheses are displayed as proposed by Muse Spark. Use &ldquo;✎ Edit&rdquo; on any object or step to refine labels before activation.
                    </p>
                  ) : (
                    <div className="revision-trail-list">
                      {candidateRevisions.map((rev) => (
                        <div className="revision-trail-item" key={rev.id}>
                          <div className="revision-meta">
                            <span className={`revision-type-chip ${rev.targetType}`}>
                              {rev.targetType === "object" ? "OBJECT" : "STEP"}
                            </span>
                            <span className="revision-time">
                              {new Date(rev.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                            </span>
                          </div>
                          <div className="revision-diff">
                            <del className="revision-original">{rev.originalValue}</del>
                            <span className="revision-arrow">→</span>
                            <ins className="revision-revised">{rev.revisedValue}</ins>
                          </div>
                          <button
                            type="button"
                            className="text-action revision-revert-btn"
                            onClick={() => handleRevertRevision(rev.id)}
                            title="Revert back to original model value"
                          >
                            Revert ↺
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
                <div className="candidate-actions">
                  <label><input type="checkbox" checked={candidateReviewed} onChange={(event) => setCandidateReviewed(event.target.checked)} /><span>I reviewed the steps and evidence. A single clip does not prove that its order is required.</span></label>
                  <button className="primary-button" disabled={!candidateReviewed || learnedProcess.transitions.length === 0} onClick={loadReviewedCandidate}>Use reviewed model <span>→</span></button>
                  {activeProcess && activeProcess !== learnedProcess && <button className="text-action" onClick={() => { setLearnedProcess(null); setCandidateReviewed(false); }}>Keep current active model ({activeProcess.task_summary}) ✕</button>}
                </div>
              </section>}
            </section>
            <aside className="card learn-card"><div className="eyebrow">WHAT THE MODEL CONTAINS</div><h3>Review before use.</h3><p>SHOWME proposes these details from the clip. Check names, steps, evidence, and open questions before loading the model.</p><div className="learn-steps">{["Objects in view", "Actions shown", "Before and after states", "Ordering observations", "Uncertain details"].map((item, index) => <div key={item}><span>{String(index + 1).padStart(2, "0")}</span>{item}</div>)}</div><div className="model-foot"><span className="status-dot muted" /> Model claims need human review</div></aside>
          </div>}

          {mode === "do" && <div className="work-grid do-grid">
            <section className="card camera-card"><div className="card-heading"><div><div className="eyebrow">CHECK A LEARNER ATTEMPT</div><h2>Show the task area.</h2></div><span className={`record-indicator ${recordingAttempt ? "recording" : ""}`}><i /> {recordingAttempt ? "RECORDING" : cameraOn ? "CAMERA ON" : "CAMERA OFF"}</span></div>
              <div className="camera-stage">{cameraOn ? <video ref={videoRef} className="camera-feed" autoPlay muted playsInline /> : <div className="camera-empty"><span>◎</span><strong>Your workspace will appear here</strong><small>Camera preview stays on this device.</small></div>}<div className="camera-crosshair" /></div>
              <div className="camera-controls">{cameraOn ? <><button className="secondary-button" onClick={stopCamera}>{recordingAttempt ? "Stop and use clip" : "Stop camera"}</button><button className="primary-button" disabled={recordingAttempt} onClick={() => void startAttemptRecording()}>{recordingAttempt ? "Recording…" : "Record this attempt"}<span>●</span></button></> : <><button className="secondary-button" onClick={() => void startCamera()}>Start camera preview</button><button className="primary-button" onClick={() => void startAttemptRecording()}>Record this attempt<span>●</span></button></>}<button className="secondary-button" disabled={!cameraOn || recordingAttempt || !activeProcess || checkingSnapshot} onClick={() => void checkCurrentState()}>{checkingSnapshot ? "Checking frame…" : "Check this frame"}</button><span className="small-note">A frame check sends one still image to Muse Spark. It uses API credits and does not track actions between checks.</span></div>
              {cameraError && <div className="inline-honesty">{cameraError}</div>}
              {snapshotError && <div className="rejected-result" role="alert"><span className="eyebrow">FRAME CHECK FAILED</span><strong>The analysis could not complete</strong><p>{snapshotError}</p>{checkpoint.state && <small>Previous trustworthy state: {checkpoint.state.label}</small>}<small>You can retry with a clearer view. This error does not affect your checkpoint history.</small></div>}
              {checkingSnapshot && <div className="checking-state" role="status" aria-live="polite"><span className="eyebrow">CHECKING FRAME</span><p>Sending this frame to Muse Spark for state comparison…</p></div>}
              {activeProcess && snapshotHistory.length > 0 && <section className="task-checkpoint" aria-label="Task checkpoint" aria-live="polite">
                <span className="eyebrow">CONTINUE FROM A FRAME CHECK</span>
                <h3>{checkpoint.current ? checkpoint.terminal ? "Inspect the modeled end state" : "Review your next step" : "Check your current position"}</h3>
                {checkpoint.state ? <p><strong>{checkpoint.current ? "Latest matched state: " : "Last matched state: "}</strong>{checkpoint.state.label}<small>Checked at {checkpoint.lastMatch && new Date(checkpoint.lastMatch.checkedAt).toLocaleTimeString()}</small></p> : <p>No declared state has matched a frame yet.</p>}
                {!checkpoint.current && <p>The current view is unconfirmed. Make the relevant parts visible and check another frame before following the next step.</p>}
                {checkpoint.nextAction && <div className="task-next-action"><strong>Next in the reviewed model: {checkpoint.nextAction.label}</strong><p>Parts: {checkpoint.nextAction.objectIds.map((id) => model.objects.find((part) => part.id === id)?.name ?? id).join(" + ")}</p>
                  {nextCheckpointState && <><span>Compare the result with:</span><p>{nextCheckpointState.label}</p>{Boolean(nextCheckpointState.observableFacts?.length) && <ul>{nextCheckpointState.observableFacts?.map((fact, index) => <li key={index}>{fact}</li>)}</ul>}</>}
                  {checkpoint.nextAction.evidence?.[0] && <small>Demonstration evidence: {checkpoint.nextAction.evidence[0].startSeconds.toFixed(1)}–{checkpoint.nextAction.evidence[0].endSeconds.toFixed(1)}s · {checkpoint.nextAction.evidence[0].observation}</small>}
                </div>}
                {checkpoint.ambiguous && <p>This state has several possible next actions. Inspect the reviewed process before choosing one.</p>}
                {checkpoint.terminal && <p>This matches a state with no further modeled action. Inspect the physical assembly before treating the task as complete.</p>}
                <small>A matched frame does not prove earlier steps were performed or that a mistake was repaired. Guidance uses the reviewed model; check its claims against the task.</small>
              </section>}

              {snapshotObservation && <section className={`snapshot-result snapshot-${snapshotObservation.assessment}`} aria-live="polite"><div className="eyebrow">ONE-FRAME CHECK · {snapshotObservation._run?.model ?? "MUSE SPARK"}</div><strong>{snapshotObservation.assessment === "consistent" ? "Matches a demonstrated state" : snapshotObservation.assessment === "possible_divergence" ? "Possible difference from the demonstrated states" : "The frame is unclear"}</strong><p>{snapshotObservation.evidence}</p><small>{snapshotObservation.state_id === "unknown" ? "No matching state identified" : activeProcess?.states.find((state) => state.id === snapshotObservation.state_id)?.description ?? snapshotObservation.state_id} · {objectLabels(snapshotObservation.object_ids)}</small>{snapshotObservation.uncertainties.length > 0 && <ul>{snapshotObservation.uncertainties.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>}{snapshotObservation.assessment === "unclear" && snapshotObservation.view_guidance && <div className="snapshot-view-guidance"><p><strong>Try this:</strong> {snapshotObservation.view_guidance}</p><button className="text-action" disabled={!cameraOn || checkingSnapshot} onClick={() => void checkCurrentState()}>{checkingSnapshot ? "Checking clearer view…" : "Check the camera again →"}</button></div>}<small className="snapshot-boundary">A still frame cannot show what happened before it or confirm recovery. This is not continuous tracking.</small>
                {snapshotFrame && activeProcess && snapshotObservation.object_ids.some((id) => id !== "unknown" && activeProcess.objects.some((object) => object.id === id)) && <div className="grounding-panel"><div className="eyebrow">FIND AN OBJECT IN THIS FRAME</div><p>SAM marks pixels that match the object Muse named. This optional check uses API credits; it does not confirm the task state.</p><div className="grounding-controls"><select aria-label="Object to locate" value={groundingObjectId} onChange={(event) => setGroundingObjectId(event.target.value)}>{snapshotObservation.object_ids.filter((id) => id !== "unknown").map((id) => activeProcess.objects.find((object) => object.id === id)).filter((object): object is LearnedProcess["objects"][number] => Boolean(object)).map((object) => <option value={object.id} key={object.id}>{object.label}</option>)}</select><button className="secondary-button" disabled={!groundingObjectId || groundingBusy} onClick={() => void groundSnapshotObject()}>{groundingBusy ? "Finding object…" : "Find object in frame"}</button></div>
                  {groundingError && <div className="inline-honesty" role="alert">{groundingError}</div>}
                  {grounding && <><SamOverlayPreview grounding={grounding} sourceImage={snapshotFrame.dataUrl} /><small className="snapshot-boundary">SAM marks visual regions matching the chosen phrase; it does not verify the task state or prove why a step is wrong.</small></>}
                </div>}
                {snapshotCanContinue && <button className="text-action snapshot-simulate" onClick={startSimulationFromSnapshot}>Explore remaining steps from this observed state →</button>}</section>}
              {snapshotHistory.length > 0 && <section className="snapshot-history" aria-label="Camera check history">
                <div className="snapshot-history-heading"><div><span className="eyebrow">FRAME CHECK HISTORY</span><small>Last {snapshotHistory.length} manual checks</small></div><button className="text-action" onClick={() => { setSnapshotHistory([]); setSnapshotObservation(null); }}>Clear checks</button></div>
                <ol className="snapshot-history-list" aria-live="polite">{[...snapshotHistory].reverse().map(({ checkedAt, observation: item }) => <li className={`snapshot-history-item history-${item.assessment}`} key={checkedAt}>
                  <span className="history-marker" aria-hidden="true" />
                  <div className="history-body"><div className="history-meta"><time dateTime={checkedAt}>{checkedAt.slice(11, 16)} UTC</time><strong>{item.assessment === "consistent" ? "MATCH" : item.assessment === "possible_divergence" ? "POSSIBLE DIFFERENCE" : "UNCLEAR"}</strong></div>
                    <p>{item.state_id === "unknown" ? "No matching state identified" : activeProcess?.states.find((candidate) => candidate.id === item.state_id)?.description ?? item.state_id.replaceAll("_", " ")}{item.object_ids.length > 0 && ` · ${objectLabels(item.object_ids)}`}</p><small>{item.evidence}</small>
                  </div>
                </li>)}</ol>
                <p className="snapshot-history-boundary">These are separate, user-requested frame checks. SHOWME does not observe the actions between them or infer recovery from this list.</p>
              </section>}
              <div className="observe-panel"><div className="eyebrow">ANALYZE A RECORDED ATTEMPT</div><h3>Compare a learner video.</h3><p>SHOWME reports timestamped differences against the reviewed model. Inspect the frames before treating a report as correct.</p>
                <button className="upload-drop compact-drop" disabled={cameraOn} onClick={() => learnerInput.current?.click()}><span className="upload-symbol">↥</span><strong>{learnerFile ? learnerFile.name : "Choose a learner video"}</strong><small>MP4, MOV, M4V, or WebM · up to 100 MB</small></button>
                <input ref={learnerInput} type="file" accept="video/mp4,video/quicktime,video/x-m4v,video/webm" hidden onChange={(event) => chooseLearnerVideo(event.target.files?.[0])} />
                {learnerUrl && <><VideoPreview src={learnerUrl} videoRef={learnerVideoRef} /><a className="text-action clip-download" href={learnerUrl} download={learnerFile?.name || "showme-attempt.webm"}>Save learner clip ↓</a></>}
                <div className="reference-upload">
                  <label className="field-label" htmlFor="observe-reference-pdf">ADD TASK INSTRUCTIONS REFERENCE (OPTIONAL)</label>
                  <input ref={observeReferenceInput} id="observe-reference-pdf" type="file" accept="application/pdf,.pdf" onChange={(event) => setObserveReferencePdf(event.target.files?.[0] ?? null)} />
                  <small>Attach an official instruction manual to ground step comparison. Sending this file uses additional API tokens.</small>
                  {observeReferencePdf && <button className="text-action" onClick={() => { setObserveReferencePdf(null); if (observeReferenceInput.current) observeReferenceInput.current.value = ""; }}>Remove instructions PDF ✕</button>}
                </div>
                <div className="capture-actions"><span className="small-note">Analysis sends this clip{observeReferencePdf ? " and instructions PDF" : ""} to Meta and may use API credits.</span><button className="primary-button" disabled={!learnerFile || !activeProcess || observing || cameraOn} onClick={() => void observeLearnerVideo()}>{observing ? "Analyzing video…" : "Analyze learner video"}<span>→</span></button></div>
                <div className="process-import"><input ref={observationInput} type="file" accept="application/json,.json" hidden onChange={(event) => void importSavedObservation(event.target.files?.[0] ?? null)} /><button className="text-action" disabled={!activeProcess} onClick={() => observationInput.current?.click()}>Load a saved learner review ↓</button><small>Import a previous JSON result to inspect its timestamps without another model call.</small></div>
                {observationImportError && <div className="inline-honesty" role="alert">{observationImportError}</div>}
                {!activeProcess && <div className="inline-honesty">Record a task video in Teach, review the proposed steps, then load the model here.</div>}
                {observeError && <div className="inline-honesty" role="alert">{observeError}</div>}
                  {observation && <section className="observation-results" aria-live="polite"><button className="text-action" onClick={saveLearnerReview}>Save learner review ↓</button><div className="observation-heading"><div><div className="eyebrow">VIDEO REVIEW · {observation._run?.model ?? "MUSE SPARK"}</div><h4>{observation.recovery_status === "recovered" && !reportedRecoveryEvent ? "Recovery unverified" : observation.recovery_status.replaceAll("_", " ")}</h4></div></div>
                  {(() => {
                    const recoveryEvent = reportedRecoveryEvent;
                    const affectedObjectIds = Array.from(new Set(observation.divergences.flatMap((d) => d.object_ids))).filter((id) => id !== "unknown");
                    const lastDivergence = observation.divergences.length > 0
                      ? Math.max(...observation.divergences.map((item) => item.time_seconds))
                      : null;
                    const recoveryCopy = {
                      no_divergence_observed: ["No divergence reported", "This clip did not produce a visible difference from the reviewed process."],
                      underway: ["Recovery may be underway", "The clip includes a divergence, but SHOWME did not confirm a later process-consistent state."],
                      recovered: recoveryEvent
                        ? ["The affected parts later matched the model", "Inspect the cited frame to verify the reported recovery."]
                        : ["Recovery evidence is incomplete", "This saved report lacks a later matching state for the affected parts after the final difference."],
                      unclear: ["Recovery is unclear", "The available frames do not support a reliable conclusion about the final state."],
                    }[observation.recovery_status];
                    return (
                      <div className={`recovery-summary recovery-${observation.recovery_status}`}>
                        <span className="eyebrow">RECOVERY EVIDENCE CHECK</span>
                        <strong>{recoveryCopy[0]}</strong>
                        <p>{recoveryCopy[1]}</p>
                        {affectedObjectIds.length > 0 && (
                          <div className="recovery-affected">
                            <span>PARTS AFFECTED</span>
                            <strong>{objectLabels(affectedObjectIds)}</strong>
                          </div>
                        )}
                        <div className="recovery-nav">
                          {lastDivergence !== null && (
                            <button className="text-action" onClick={() => inspectLearnerEvidence(lastDivergence)}>
                              Jump to latest difference · {lastDivergence.toFixed(1)}s →
                            </button>
                          )}
                          {recoveryEvent && (
                            <button className="text-action" onClick={() => inspectLearnerEvidence(recoveryEvent.time_seconds)}>
                              Inspect reported recovery · {recoveryEvent.time_seconds.toFixed(1)}s →
                            </button>
                          )}
                        </div>
                        <small className="snapshot-boundary">Recovery requires later visible evidence showing all affected parts returned to a valid modeled state. Clicking continue or running a simulation is not recovery evidence.</small>
                      </div>
                    );
                  })()}
                  <p className="evidence-review-hint">Select a timestamp to inspect the supporting moment. Locate sends one frame and one object phrase to SAM, using API credits; it segments pixels but does not verify the reported difference.</p>
                  {observation.reference_checks.length > 0 && <div className="reference-step-checks"><strong>Manual step review · {observation.reference_checks.length}</strong>{observation.reference_checks.map((check) => {
                    const transition = activeProcess?.transitions.find((item) => item.id === check.transition_id);
                    const statusCopy = { matches_reference: "Visible match", possible_mismatch: "Possible mismatch", not_shown: "Not shown in clip", unclear: "Need a clearer view" }[check.status];
                    return <article className={`reference-step-check reference-${check.status}`} key={check.transition_id}><div className="reference-step-heading"><b>{transition?.action ?? check.transition_id}</b><span>{statusCopy}</span></div><p>{check.evidence}</p>{transition?.reference_evidence?.map((citation, index) => <small key={`${check.transition_id}-${index}`}>Manual p. {citation.page}, step {citation.step}: {citation.observation}</small>)}{check.time_seconds !== null && <button className="text-action" onClick={() => inspectLearnerEvidence(check.time_seconds!)}>Inspect clip at {check.time_seconds.toFixed(1)}s →</button>}{check.next_guidance && <p className="reference-next"><strong>Next:</strong> {check.next_guidance}</p>}</article>;
                  })}</div>}
                  {observation.divergences.length > 0 && <div className="divergence-list"><strong>Differences to inspect · {observation.divergences.length}</strong>{observation.divergences.map((item, index) => <div className="divergence-entry" key={`${item.time_seconds}-${index}`}><button className="evidence-row" onClick={() => inspectLearnerEvidence(item.time_seconds)}><span>{item.time_seconds.toFixed(1)}s</span><div><b>{item.process_difference}</b><p>{item.evidence}</p><small>{objectLabels(item.object_ids)}</small></div></button>{item.object_ids.filter((id) => id !== "unknown" && activeProcess?.objects.some((object) => object.id === id)).map((id) => <button className="ground-evidence-button" disabled={learnerGroundingBusy} key={id} onClick={() => void groundLearnerEvidence(item.time_seconds, id)}>Find {activeProcess?.objects.find((object) => object.id === id)?.label ?? id} in frame</button>)}</div>)}</div>}
                  {learnerGroundingError && <div className="inline-honesty" role="alert">{learnerGroundingError}</div>}
                  {learnerGroundingBusy && <p className="evidence-review-hint">Opening the selected video moment and looking for the object…</p>}
                  {learnerGrounding && <div className="learner-grounding-result"><div className="eyebrow">CLIP FRAME · {learnerGrounding.seconds.toFixed(1)}s · {activeProcess?.objects.find((object) => object.id === learnerGrounding.objectId)?.label ?? learnerGrounding.objectId}</div><SamOverlayPreview grounding={learnerGrounding.result} sourceImage={learnerGrounding.dataUrl} /><small className="snapshot-boundary">This is SAM segmentation on one Muse-referenced clip timestamp. It does not independently confirm the reported divergence.</small></div>}
                  <div className="observed-events"><strong>Observed events · {observation.events.length}</strong>{observation.events.map((item, index) => <button className="evidence-event" key={`${item.time_seconds}-${index}`} onClick={() => inspectLearnerEvidence(item.time_seconds)}><span>{item.time_seconds.toFixed(1)}s</span><i className={`event-dot ${item.assessment}`} /><div><b>{item.action}</b><p>{item.evidence}</p><small>{objectLabels(item.object_ids)}</small></div><small>{item.assessment.toUpperCase()}</small></button>)}</div>
                  {observation.uncertainties.length > 0 && <div className="candidate-uncertainties"><strong>Uncertain from this clip</strong><ul>{observation.uncertainties.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div>}
                </section>}
              </div>
            </section>
            <aside className="card guide-card"><div className="eyebrow">{activeProcess ? "REVIEWED TASK MODEL" : "SAMPLE PROCEDURE"}</div><h3>{activeProcess ? "Steps from your video." : "Example steps."}</h3>{!activeProcess && <p className="model-copy">This sample was not learned from a video. Teach a task to create your own model.</p>}<div className="guide-list">{model.actions.map((action, index) => <div className="guide-step" key={action.id}><span className="guide-check">{String(index + 1).padStart(2, "0")}</span><div><strong>{action.label}</strong><small>{action.explanation}</small></div></div>)}</div><div className="guide-boundary"><span>i</span><p>Camera preview stays local. SHOWME checks a frame only when you ask and does not watch actions continuously.</p></div><button className="text-action" onClick={() => setMode("simulate")}>Test a step order →</button>{activeProcess && <button className="text-action forget-skill" onClick={forgetReviewedSkill}>Remove saved model</button>}</aside>
          </div>}

          <footer className="page-footer"><span>SHOWME · DEMONSTRATION → PROCESS MODEL → GUIDANCE</span><span>PROTOTYPE BUILD · 2026</span></footer>
        </div>
      </section>
    </main>
  );
}
