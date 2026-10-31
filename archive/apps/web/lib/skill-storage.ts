const STORAGE_KEY = "showme.reviewed-skill.v1";

export type SavedProcess = {
  task_summary: string;
  objects: { id: string; label: string; visual_description: string }[];
  states: { id: string; description: string; observable_facts: string[] }[];
  transitions: {
    id: string;
    action: string;
    object_ids: string[];
    from_state: string;
    to_state: string;
    candidate_constraints?: string[];
    /** Compatibility for locally saved v1 candidates. */
    preconditions?: string[];
    postconditions: string[];
    evidence: { start_seconds: number; end_seconds: number; observation: string }[];
    reference_evidence?: { page: number; step: string; observation: string }[];
  }[];
  /** Explicit user mappings from a model suggestion to an observed state. */
  human_confirmed_constraints?: { transition_id: string; candidate_constraint_index?: number; precondition_index?: number; required_state: string }[];
  ordering_observations: { before_transition_id: string; after_transition_id: string; evidence: { start_seconds: number; end_seconds: number; observation: string }[] }[];
  uncertainties: string[];
  _run?: { model?: string; usage?: { input_tokens?: number; output_tokens?: number }; source?: { duration_seconds?: number }; reference_filename?: string | null };
  _validation?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isSavedProcess(value: unknown): value is SavedProcess {
  if (!isRecord(value) || typeof value.task_summary !== "string" || !Array.isArray(value.objects) || !Array.isArray(value.states) || !Array.isArray(value.transitions) || !Array.isArray(value.ordering_observations) || !Array.isArray(value.uncertainties)) return false;
  const isEvidence = (item: unknown) => isRecord(item) && typeof item.start_seconds === "number" && Number.isFinite(item.start_seconds) && typeof item.end_seconds === "number" && Number.isFinite(item.end_seconds) && typeof item.observation === "string";
  if (!value.objects.every((item) => isRecord(item) && typeof item.id === "string" && typeof item.label === "string" && typeof item.visual_description === "string")) return false;
  if (!value.states.every((item) => isRecord(item) && typeof item.id === "string" && typeof item.description === "string" && Array.isArray(item.observable_facts) && item.observable_facts.every((fact) => typeof fact === "string"))) return false;
  if (!value.transitions.every((item) => {
    if (!isRecord(item)) return false;
    const constraints = item.candidate_constraints ?? item.preconditions;
    return typeof item.id === "string"
      && typeof item.action === "string"
      && typeof item.from_state === "string"
      && typeof item.to_state === "string"
      && Array.isArray(item.object_ids)
      && item.object_ids.every((id) => typeof id === "string")
      && Array.isArray(constraints)
      && constraints.every((fact) => typeof fact === "string")
      && Array.isArray(item.postconditions)
      && item.postconditions.every((fact) => typeof fact === "string")
      && Array.isArray(item.evidence)
      && item.evidence.every(isEvidence)
      && (item.reference_evidence === undefined || (Array.isArray(item.reference_evidence) && item.reference_evidence.every((source) => isRecord(source) && Number.isInteger(source.page) && Number(source.page) >= 1 && typeof source.step === "string" && typeof source.observation === "string")));
  })) return false;
  if (value.human_confirmed_constraints !== undefined) {
    const mappings = value.human_confirmed_constraints;
    if (!Array.isArray(mappings) || !mappings.every((item) => {
      if (!isRecord(item)) return false;
      const index = item.candidate_constraint_index ?? item.precondition_index;
      return typeof item.transition_id === "string"
        && Number.isInteger(index)
        && Number(index) >= 0
        && typeof item.required_state === "string";
    })) return false;
    const typedMappings = mappings as NonNullable<SavedProcess["human_confirmed_constraints"]>;
    const transitions = value.transitions as SavedProcess["transitions"];
    const stateIds = new Set((value.states as SavedProcess["states"]).map((item) => item.id));
    if (!typedMappings.every((item) => {
      const transition = transitions.find((candidate) => candidate.id === item.transition_id);
      const index = item.candidate_constraint_index ?? item.precondition_index ?? -1;
      return Boolean(transition && index < (transition.candidate_constraints ?? transition.preconditions ?? []).length && stateIds.has(item.required_state));
    })) return false;
  }
  if (!value.ordering_observations.every((item) => isRecord(item) && typeof item.before_transition_id === "string" && typeof item.after_transition_id === "string" && Array.isArray(item.evidence) && item.evidence.every(isEvidence))) return false;
  return value.uncertainties.every((item) => typeof item === "string");
}

export function loadReviewedProcess(): SavedProcess | null {
  try {
    const serialized = localStorage.getItem(STORAGE_KEY);
    if (!serialized) return null;
    const saved: unknown = JSON.parse(serialized);
    if (!isRecord(saved) || saved.version !== 1 || !isSavedProcess(saved.process)) return null;
    return saved.process;
  } catch {
    return null;
  }
}

export function saveReviewedProcess(process: SavedProcess) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, process }));
  } catch {
    // Storage may be unavailable or full; the in-memory skill remains usable.
  }
}

export function clearReviewedProcess() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Clearing local persistence is best effort in restricted browser contexts.
  }
}
