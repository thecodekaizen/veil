import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function loadTypeScript(relativePath) {
  const source = await readFile(new URL(relativePath, import.meta.url), "utf8");
  const javascript = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);
}

const { simulateAction, simulateSequence, resolveSimulationRecovery, repairSequenceOrder, testRepairedSequence } = await loadTypeScript("../lib/simulate.ts");
const { processToSkill } = await loadTypeScript("../lib/process-to-skill.ts");
const { isSavedProcess } = await loadTypeScript("../lib/skill-storage.ts");

function savedProcess(constraintField) {
  return {
    task_summary: "Attach a part",
    objects: [{ id: "part", label: "Part", visual_description: "A small part." }],
    states: [{ id: "start", description: "Part is loose.", observable_facts: [] }],
    transitions: [{
      id: "attach-part",
      action: "Attach part",
      object_ids: ["part"],
      from_state: "start",
      to_state: "start",
      [constraintField]: ["The support may need to be attached first."],
      postconditions: ["The attached part is visibly seated."],
      evidence: [{ start_seconds: 1, end_seconds: 2, observation: "The part is handled." }],
    }],
    ordering_observations: [],
    uncertainties: [],
  };
}

test("saved process accepts unverified candidate constraints", () => {
  assert.equal(isSavedProcess(savedProcess("candidate_constraints")), true);
});

test("saved process keeps previously saved precondition candidates readable", () => {
  assert.equal(isSavedProcess(savedProcess("preconditions")), true);
});

function modelFor(constraint, { fromState = "start" } = {}) {
  return {
    id: "test-skill",
    title: "Test skill",
    status: "learned-from-demonstration",
    objects: [],
    initialState: ["start"],
    actions: [{
      id: "attach-part",
      label: "Attach part",
      objectIds: ["part"],
      constraints: constraint ? [constraint] : [],
      produces: ["attached"],
      fromState,
      toState: "attached",
      explanation: "Attach the part.",
      recovery: "Return to the demonstrated state.",
    }],
  };
}

test("a proposed constraint stays visible but does not block a transition", () => {
  const proposed = {
    id: "possible-support-order",
    description: "The support may need to be attached first.",
    status: "proposed",
    source: "model-hypothesis",
  };

  const result = simulateAction(modelFor(proposed), ["start"], "attach-part");

  assert.equal(result.accepted, true);
  assert.deepEqual(result.state, ["attached"]);
});

test("a confirmed constraint blocks with the missing state and its provenance", () => {
  const confirmed = {
    id: "support-before-part",
    requiredState: "support-attached",
    status: "confirmed",
    source: "expert-narration",
    evidence: [{ startSeconds: 2, endSeconds: 3, observation: "Expert says the support must be attached first." }],
  };

  const result = simulateAction(modelFor(confirmed), ["start"], "attach-part");

  assert.equal(result.accepted, false);
  assert.equal(result.kind, "blocked");
  assert.deepEqual(result.missing, ["support-attached"]);
  assert.equal(result.blockedBy[0].source, "expert-narration");
});

test("an unobserved action order is reported as unknown, not as a confirmed violation", () => {
  const result = simulateAction(modelFor(undefined, { fromState: "other-state" }), ["start"], "attach-part");

  assert.equal(result.accepted, false);
  assert.equal(result.kind, "unobserved");
  assert.equal(result.missing[0], "other-state");
});

test("candidate constraints from one learned trace stay proposed when converted to the shared model", () => {
  const skill = processToSkill({
    task_summary: "Attach a part",
    objects: [
      { id: "part", label: "Part", visual_description: "A small part." },
      { id: "support", label: "Support", visual_description: "A support piece." },
    ],
    states: [{ id: "start", description: "Part is loose." }, { id: "attached", description: "Part is attached." }],
    transitions: [{
      id: "attach-part",
      action: "Attach part",
      object_ids: ["part", "support"],
      from_state: "start",
      to_state: "attached",
      candidate_constraints: ["Support may need to be attached first."],
      postconditions: ["The attached part is visibly seated."],
      evidence: [{ start_seconds: 1, end_seconds: 2, observation: "The part is attached." }],
    }],
  });

  assert.deepEqual(skill.actions[0].objectIds, ["part", "support"]);
  assert.deepEqual(skill.actions[0].constraints, [{
    id: "attach-part-hypothesis-1",
    description: "Support may need to be attached first.",
    status: "proposed",
    source: "model-hypothesis",
  }]);
  assert.deepEqual(skill.actions[0].produces, ["attached"]);
  assert.equal(simulateAction(skill, ["start"], "attach-part").accepted, true);
});

test("an explicit human mapping promotes only that candidate constraint", () => {
  const skill = processToSkill({
    task_summary: "Attach a part",
    objects: [{ id: "part", label: "Part", visual_description: "A small part." }],
    states: [{ id: "start", description: "Part is loose." }, { id: "support-ready", description: "Support is attached." }, { id: "attached", description: "Part is attached." }],
    transitions: [{
      id: "attach-part",
      action: "Attach part",
      object_ids: ["part"],
      from_state: "start",
      to_state: "attached",
      candidate_constraints: ["Support may need to be attached first.", "The part appears visible in this trace."],
      postconditions: [],
      evidence: [],
    }],
    human_confirmed_constraints: [{ transition_id: "attach-part", candidate_constraint_index: 0, required_state: "support-ready" }],
  });

  assert.deepEqual(skill.actions[0].constraints.map((constraint) => constraint.status), ["confirmed", "proposed"]);
  assert.equal(skill.actions[0].constraints[0].requiredState, "support-ready");
  assert.equal(skill.actions[0].constraints[0].source, "human-confirmation");
  assert.equal(simulateAction(skill, ["start"], "attach-part").kind, "blocked");
});

test("sequence simulation stops at the first confirmed prerequisite and preserves the last valid state", () => {
  const model = {
    id: "stacked-skill",
    title: "Stack the pieces",
    status: "illustrative-fixture",
    initialState: ["base-ready", "support-available"],
    objects: [],
    actions: [
      { id: "place-support", label: "Place support", objectIds: ["support"], constraints: [], produces: ["support-seated"], explanation: "Seat the support.", recovery: "Reset." },
      { id: "attach-cap", label: "Attach cap", objectIds: ["cap"], constraints: [{ id: "support-first", description: "The support must be seated first.", requiredState: "support-seated", status: "confirmed", source: "human-confirmation" }], produces: ["cap-attached"], explanation: "Attach the cap.", recovery: "Remove the cap and seat the support." },
    ],
  };

  const result = simulateSequence(model, ["attach-cap", "place-support"]);

  assert.equal(result.status, "blocked");
  assert.equal(result.steps.length, 1);
  assert.equal(result.finalState.includes("support-seated"), false);
  assert.equal(result.steps[0].result.kind, "blocked");
  assert.equal(result.steps[0].result.blockedBy[0].source, "human-confirmation");
});

test("a learned sequence that departs from its observed starting state is unknown, not impossible", () => {
  const model = modelFor(undefined, { fromState: "after-support" });
  const result = simulateSequence(model, ["attach-part"]);

  assert.equal(result.status, "unobserved");
  assert.deepEqual(result.finalState, ["start"]);
});

test("a sequence can explicitly start from a recognized non-initial state", () => {
  const model = modelFor(undefined, { fromState: "recognized-state" });
  const result = simulateSequence(model, ["attach-part"], ["recognized-state"]);

  assert.equal(result.status, "completed");
  assert.deepEqual(result.initialState, ["recognized-state"]);
  assert.deepEqual(result.finalState, ["attached"]);
});


test("reviewed state relationships survive conversion without sharing mutable arrays", () => {
  const candidate = savedProcess("candidate_constraints");
  candidate.states[0].observable_facts = ["The clip faces the mating connector."];
  const model = processToSkill(candidate);
  assert.deepEqual(model.states[0].observableFacts, candidate.states[0].observable_facts);
  model.states[0].observableFacts.push("Temporary simulator annotation");
  assert.equal(candidate.states[0].observable_facts.length, 1);
});

test("older candidates without visible facts remain readable without invented relationships", () => {
  const candidate = savedProcess("candidate_constraints");
  delete candidate.states[0].observable_facts;
  assert.deepEqual(processToSkill(candidate).states[0].observableFacts, []);
});

test("resolveSimulationRecovery checks whether candidate action can execute now", () => {
  const model = {
    id: "multi-step",
    title: "Multi step",
    status: "learned-from-demonstration",
    objects: [],
    initialState: ["start"],
    states: [{ id: "step1", label: "Step 1 Done" }, { id: "step2", label: "Step 2 Done" }, { id: "step0", label: "Step 0" }],
    actions: [
      { id: "action-1", label: "Action 1", objectIds: [], constraints: [{ id: "c0", requiredState: "step0", status: "confirmed", source: "human-confirmation" }], produces: ["step1"] },
      { id: "action-2", label: "Action 2", objectIds: [], constraints: [{ id: "c1", requiredState: "step1", status: "confirmed", source: "human-confirmation" }], produces: ["step2"] },
    ],
  };

  const blockedResult = simulateAction(model, ["start"], "action-2");
  assert.equal(blockedResult.accepted, false);
  const recovery = resolveSimulationRecovery(model, blockedResult, ["start"]);
  assert.equal(recovery.length, 1);
  assert.equal(recovery[0].candidates.length, 1);
  assert.equal(recovery[0].candidates[0].action.id, "action-1");
  // action-1 requires step0, which is missing from ["start"], so canExecuteNow must be false
  assert.equal(recovery[0].candidates[0].canExecuteNow, false);
  assert.deepEqual(recovery[0].candidates[0].unmetPrerequisites, ["step0"]);
});

test("resolveSimulationRecovery handles multiple candidate actions explicitly", () => {
  const model = {
    id: "branching-recovery",
    title: "Branching recovery",
    status: "learned-from-demonstration",
    objects: [],
    initialState: ["start"],
    states: [{ id: "ready", label: "Ready" }, { id: "done", label: "Done" }],
    actions: [
      { id: "route-a", label: "Route A", objectIds: [], constraints: [], produces: ["ready"] },
      { id: "route-b", label: "Route B", objectIds: [], constraints: [], produces: ["ready"] },
      { id: "final-step", label: "Final Step", objectIds: [], constraints: [{ id: "c", requiredState: "ready", status: "confirmed", source: "human-confirmation" }], produces: ["done"] },
    ],
  };

  const blockedResult = simulateAction(model, ["start"], "final-step");
  const recovery = resolveSimulationRecovery(model, blockedResult, ["start"]);
  assert.equal(recovery[0].candidates.length, 2);
  assert.equal(recovery[0].candidates[0].action.id, "route-a");
  assert.equal(recovery[0].candidates[0].canExecuteNow, true);
  assert.equal(recovery[0].candidates[1].action.id, "route-b");
  assert.equal(recovery[0].candidates[1].canExecuteNow, true);
  assert.match(recovery[0].explanation, /Multiple modeled actions/);
});

test("testRepairedSequence reruns the sequence and displays remaining blockers", () => {
  const model = {
    id: "chained-requirements",
    title: "Chained requirements",
    status: "learned-from-demonstration",
    objects: [],
    initialState: ["start"],
    states: [{ id: "p1", label: "Prereq 1" }, { id: "p2", label: "Prereq 2" }, { id: "done", label: "Done" }],
    actions: [
      { id: "act-1", label: "Action 1", objectIds: [], constraints: [], produces: ["p1"] },
      { id: "act-2", label: "Action 2", objectIds: [], constraints: [{ id: "c1", requiredState: "p1", status: "confirmed", source: "human-confirmation" }], produces: ["p2"] },
      { id: "act-3", label: "Action 3", objectIds: [], constraints: [{ id: "c2", requiredState: "p2", status: "confirmed", source: "human-confirmation" }], produces: ["done"] },
    ],
  };

  // If user only inserts act-2 before act-3, act-2 is now blocked by missing p1
  const testRun = testRepairedSequence(model, ["act-3"], "act-3", "act-2", ["start"]);
  assert.equal(testRun.hasRemainingBlockers, true);
  assert.match(testRun.remainingBlockerMessage, /remains blocked: missing p1/);
});

test("resolveSimulationRecovery reports unobserved transition as not established by model", () => {
  const model = {
    id: "isolated",
    title: "Isolated",
    status: "learned-from-demonstration",
    objects: [],
    initialState: ["start"],
    actions: [
      { id: "action-2", label: "Action 2", objectIds: [], constraints: [{ id: "c1", requiredState: "unproduced-state", status: "confirmed", source: "human-confirmation" }], produces: ["done"] },
    ],
  };

  const blockedResult = simulateAction(model, ["start"], "action-2");
  const recovery = resolveSimulationRecovery(model, blockedResult, ["start"]);
  assert.equal(recovery.length, 1);
  assert.equal(recovery[0].candidates.length, 0);
  assert.match(recovery[0].explanation, /cannot be resolved from the current model/);
});

test("repairSequenceOrder reorders an existing action to precede the blocked action", () => {
  const initial = ["action-b", "action-a", "action-c"];
  const repaired = repairSequenceOrder(initial, "action-b", "action-a");
  assert.deepEqual(repaired, ["action-a", "action-b", "action-c"]);
});

test("repairSequenceOrder inserts an unlisted recovery action immediately before blocked action", () => {
  const initial = ["action-b", "action-c"];
  const repaired = repairSequenceOrder(initial, "action-b", "action-a");
  assert.deepEqual(repaired, ["action-a", "action-b", "action-c"]);
});
