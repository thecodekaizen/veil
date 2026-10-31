import type { SkillAction, SkillConstraint, SkillModel } from "./skill-model";

export type SimulationResult =
  | { accepted: true; state: string[]; action: SkillAction; message: string }
  | { accepted: false; state: string[]; action: SkillAction; missing: string[]; kind: "blocked"; message: string; blockedBy: Extract<SkillConstraint, { status: "confirmed" }>[] }
  | { accepted: false; state: string[]; action: SkillAction; missing: string[]; kind: "unobserved"; message: string };

export type SequenceSimulation = {
  status: "completed" | "blocked" | "unobserved";
  initialState: string[];
  finalState: string[];
  steps: { index: number; result: SimulationResult }[];
};

/** Apply one proposed action; only confirmed constraints can block it. */
export function simulateAction(
  model: SkillModel,
  currentState: string[],
  actionId: string,
): SimulationResult {
  const action = model.actions.find((candidate) => candidate.id === actionId);
  if (!action) throw new Error(`Unknown action: ${actionId}`);

  const blockedBy = action.constraints
    .filter((constraint) => constraint.status === "confirmed")
    .filter((constraint) => !currentState.includes(constraint.requiredState));
  const missing = blockedBy.map((constraint) => constraint.requiredState);
  if (missing.length > 0) {
    return {
      accepted: false,
      state: currentState,
      action,
      missing,
      blockedBy,
      kind: "blocked",
      message: `This action cannot be completed yet. ${action.explanation}`,
    };
  }

  if (model.status === "learned-from-demonstration" && action.fromState && !currentState.includes(action.fromState)) {
    return {
      accepted: false,
      state: currentState,
      action,
      missing: [action.fromState],
      kind: "unobserved",
      message: "This transition is not established by this model. One demonstration cannot tell us whether the alternative is impossible or unsafe.",
    };
  }

  return {
    accepted: true,
    state: [...new Set([...currentState.filter((item) => item !== action.fromState), ...action.produces])],
    action,
    message: `${action.label} can proceed. ${action.explanation}`,
  };
}

export function completedActions(model: SkillModel, state: string[]) {
  return model.actions.filter((action) => action.produces.every((condition) => state.includes(condition)));
}

/** Replay a proposed order from the model start or an explicitly selected state. */
export function simulateSequence(
  model: SkillModel,
  actionIds: string[],
  startingState: string[] = model.initialState,
): SequenceSimulation {
  const initialState = [...startingState];
  let state = [...initialState];
  const steps: SequenceSimulation["steps"] = [];

  for (const [index, actionId] of actionIds.entries()) {
    const result = simulateAction(model, state, actionId);
    steps.push({ index, result });
    if (!result.accepted) {
      return {
        status: result.kind,
        initialState,
        finalState: state,
        steps,
      };
    }
    state = result.state;
  }

  return { status: "completed", initialState, finalState: state, steps };
}

export type CandidateRecoveryAction = {
  action: SkillAction;
  canExecuteNow: boolean;
  unmetPrerequisites: string[];
};

export type RecoverySuggestion = {
  missingStateId: string;
  missingStateLabel: string;
  isUnobservedTransition: boolean;
  candidates: CandidateRecoveryAction[];
  explanation: string;
};

/**
 * Identify recovery options for a blocked or unobserved simulation result.
 * Checks all actions in the model that produce the missing prerequisite,
 * verifying whether each candidate can execute from the current simulated state.
 */
export function resolveSimulationRecovery(
  model: SkillModel,
  result: Extract<SimulationResult, { accepted: false }>,
  currentState: string[] = result.state,
): RecoverySuggestion[] {
  const labelFor = (id: string) =>
    model.states?.find((s) => s.id === id)?.label ?? id.replaceAll("_", " ");
  const isUnobserved = result.kind === "unobserved";

  return result.missing.map((stateId) => {
    const matchingActions = model.actions.filter((action) => action.produces.includes(stateId));
    const candidates: CandidateRecoveryAction[] = matchingActions.map((action) => {
      const probe = simulateAction(model, currentState, action.id);
      return {
        action,
        canExecuteNow: probe.accepted,
        unmetPrerequisites: probe.accepted ? [] : probe.missing,
      };
    });

    let explanation: string;
    if (candidates.length === 0) {
      explanation = isUnobserved
        ? `This transition is not established by this model from the current state. No modeled action produces "${labelFor(stateId)}".`
        : `No modeled action produces required state "${labelFor(stateId)}". This path cannot be resolved from the current model.`;
    } else if (candidates.length === 1) {
      const c = candidates[0];
      explanation = c.canExecuteNow
        ? `Perform "${c.action.label}" first to achieve required state "${labelFor(stateId)}". This action is executable from the current state.`
        : `Action "${c.action.label}" produces "${labelFor(stateId)}", but requires prior steps: ${c.unmetPrerequisites.map(labelFor).join(", ")}.`;
    } else {
      explanation = `Multiple modeled actions produce "${labelFor(stateId)}". Review candidates below to select a recovery step.`;
    }

    return {
      missingStateId: stateId,
      missingStateLabel: labelFor(stateId),
      isUnobservedTransition: isUnobserved,
      candidates,
      explanation,
    };
  });
}

/**
 * Reorders a sequence by moving or inserting the recovery action immediately
 * before the blocked action, creating a candidate sequence.
 */
export function repairSequenceOrder(
  actionIds: readonly string[],
  blockedActionId: string,
  recoveryActionId: string,
): string[] {
  const filtered = actionIds.filter((id) => id !== recoveryActionId);
  const targetIndex = filtered.indexOf(blockedActionId);
  if (targetIndex === -1) {
    return [recoveryActionId, ...filtered];
  }
  return [
    ...filtered.slice(0, targetIndex),
    recoveryActionId,
    ...filtered.slice(targetIndex),
  ];
}

export type RepairedSequenceResult = {
  repairedActionIds: string[];
  simulation: SequenceSimulation;
  resolvedBlockedActionId: string;
  insertedActionId: string;
  hasRemainingBlockers: boolean;
  remainingBlockerMessage?: string;
};

/**
 * Reruns the repaired sequence against the model from the given starting state,
 * detecting whether the entire sequence completed or if subsequent blockers remain.
 */
export function testRepairedSequence(
  model: SkillModel,
  currentActionIds: readonly string[],
  blockedActionId: string,
  recoveryActionId: string,
  startingState: string[] = model.initialState,
): RepairedSequenceResult {
  const repairedActionIds = repairSequenceOrder(currentActionIds, blockedActionId, recoveryActionId);
  const simulation = simulateSequence(model, repairedActionIds, startingState);
  const failedEntry = simulation.steps.find((s) => !s.result.accepted);
  const failedStep = failedEntry && !failedEntry.result.accepted ? failedEntry.result : undefined;
  const hasRemainingBlockers = simulation.status !== "completed";
  const remainingBlockerMessage = hasRemainingBlockers && failedStep
    ? failedStep.kind === "unobserved"
      ? `Step "${failedStep.action.label}" is not established by this model from its simulated state.`
      : `Step "${failedStep.action.label}" remains blocked: missing ${failedStep.missing.join(", ")}.`
    : undefined;

  return {
    repairedActionIds,
    simulation,
    resolvedBlockedActionId: blockedActionId,
    insertedActionId: recoveryActionId,
    hasRemainingBlockers,
    remainingBlockerMessage,
  };
}
