import type { SkillModel } from "./skill-model";

type ProcessCandidate = {
  task_summary: string;
  objects: { id: string; label: string; visual_description: string }[];
  states: { id: string; description: string; observable_facts?: string[] }[];
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
  human_confirmed_constraints?: { transition_id: string; candidate_constraint_index?: number; precondition_index?: number; required_state: string }[];
};

/** Convert a reviewed API candidate into the shared app representation. */
export function processToSkill(
  candidate: ProcessCandidate,
): SkillModel {
  const firstTransition = candidate.transitions[0];
  return {
    id: "learned-process",
    title: candidate.task_summary,
    status: "learned-from-demonstration",
    initialState: firstTransition ? [firstTransition.from_state] : [],
    states: candidate.states.map((state) => ({ id: state.id, label: state.description, observableFacts: [...(state.observable_facts ?? [])] })),
    objects: candidate.objects.map((object, index) => ({
      id: object.id,
      name: object.label,
      color: ["amber", "blue", "copper", "stone"][index % 4],
      shape: "component",
      visualDescription: object.visual_description,
    })),
    actions: candidate.transitions.map((transition) => ({
      id: transition.id,
      label: transition.action,
      objectIds: transition.object_ids.length > 0 ? [...transition.object_ids] : ["unknown"],
      // One demonstration cannot prove a requirement. Keep candidate constraints
      // visible as hypotheses until a human confirms them.
      constraints: (transition.candidate_constraints ?? transition.preconditions ?? []).map((description, index) => {
        const confirmed = candidate.human_confirmed_constraints?.find((item) => item.transition_id === transition.id && (item.candidate_constraint_index ?? item.precondition_index) === index);
        const requiredState = candidate.states.find((item) => item.id === confirmed?.required_state);
        return requiredState
          ? { id: `${transition.id}-confirmed-${index + 1}`, description, requiredState: requiredState.id, status: "confirmed" as const, source: "human-confirmation" as const }
          : { id: `${transition.id}-hypothesis-${index + 1}`, description, status: "proposed" as const, source: "model-hypothesis" as const };
      }),
      // A demonstration gives us an observed state transition, not a set of
      // persistent world facts. Keep the simulation state on declared state IDs.
      produces: [transition.to_state],
      fromState: transition.from_state,
      toState: transition.to_state,
      explanation: transition.evidence.map((item) => item.observation).join(" "),
      recovery: "Return to a state supported by the demonstration, then review the transition evidence.",
      evidence: transition.evidence.map((item) => ({
        startSeconds: item.start_seconds,
        endSeconds: item.end_seconds,
        observation: item.observation,
      })),
    })),
  };
}
