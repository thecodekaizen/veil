import test from "node:test";
import assert from "node:assert/strict";
import { applyRevision, revertRevision } from "../lib/candidate-revision.ts";

const sampleCandidate = {
  task_summary: "Build mini starfighter",
  objects: [
    { id: "obj_1", label: "Central cockpit block", visual_description: "Dark grey 2x2 round" },
    { id: "obj_2", label: "Port wing", visual_description: "Black angled plate" },
  ],
  transitions: [
    {
      id: "step_1",
      action: "Attach port wing to cockpit",
      from_state: "start",
      to_state: "wing_attached",
      object_ids: ["obj_1", "obj_2"],
      postconditions: ["port wing secured"],
      evidence: [{ start_seconds: 1.0, end_seconds: 3.5, observation: "Learner mounts port wing" }],
    },
  ],
};

test("records revision when human edits object label", () => {
  const { process, revisions, applied } = applyRevision(
    sampleCandidate,
    [],
    "object",
    "obj_1",
    "TIE Cockpit Fuselage",
    "2026-10-28T07:00:00Z"
  );

  assert.equal(applied, true);
  assert.equal(revisions.length, 1);
  assert.equal(revisions[0].targetType, "object");
  assert.equal(revisions[0].targetId, "obj_1");
  assert.equal(revisions[0].field, "label");
  assert.equal(revisions[0].originalValue, "Central cockpit block");
  assert.equal(revisions[0].revisedValue, "TIE Cockpit Fuselage");
  assert.equal(process.objects[0].label, "TIE Cockpit Fuselage");
});

test("records revision when human edits action name", () => {
  const { process, revisions, applied } = applyRevision(
    sampleCandidate,
    [],
    "action",
    "step_1",
    "Snap port radiator wing onto cockpit bracket",
    "2026-10-28T07:01:00Z"
  );

  assert.equal(applied, true);
  assert.equal(revisions.length, 1);
  assert.equal(revisions[0].targetType, "action");
  assert.equal(revisions[0].targetId, "step_1");
  assert.equal(revisions[0].field, "action");
  assert.equal(revisions[0].originalValue, "Attach port wing to cockpit");
  assert.equal(revisions[0].revisedValue, "Snap port radiator wing onto cockpit bracket");
  assert.equal(process.transitions[0].action, "Snap port radiator wing onto cockpit bracket");
});

test("ignores identical or whitespace-only edits", () => {
  const res1 = applyRevision(sampleCandidate, [], "object", "obj_1", "Central cockpit block");
  assert.equal(res1.applied, false);
  assert.equal(res1.revisions.length, 0);

  const res2 = applyRevision(sampleCandidate, [], "object", "obj_1", "   ");
  assert.equal(res2.applied, false);
  assert.equal(res2.revisions.length, 0);
});

test("reverts revision cleanly restoring original value", () => {
  const res1 = applyRevision(
    sampleCandidate,
    [],
    "object",
    "obj_2",
    "Solar Array Wing (Left)",
    "2026-10-28T07:02:00Z"
  );
  assert.equal(res1.applied, true);
  assert.equal(res1.process.objects[1].label, "Solar Array Wing (Left)");

  const revId = res1.revisions[0].id;
  const reverted = revertRevision(res1.process, res1.revisions, revId);

  assert.equal(reverted.reverted, true);
  assert.equal(reverted.revisions.length, 0);
  assert.equal(reverted.process.objects[1].label, "Port wing");
});
