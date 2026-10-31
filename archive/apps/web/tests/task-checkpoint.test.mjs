import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";
const source = await readFile(new URL("../lib/task-checkpoint.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { taskCheckpoint } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);
const model = { states: [{ id: "start", label: "Parts laid out" }, { id: "joined", label: "Parts joined" }, { id: "done", label: "Closed" }], actions: [{ id: "join", fromState: "start", toState: "joined" }, { id: "close", fromState: "joined", toState: "done" }] };
const check = (state_id, assessment = "consistent") => ({ checkedAt: "2026-10-28T10:00:00Z", observation: { state_id, assessment } });
test("guides from the unique outgoing transition of the current match", () => {
  const result = taskCheckpoint(model, [check("joined")]);
  assert.equal(result.nextAction.id, "close");
  assert.equal(result.state.label, "Parts joined");
  assert.equal(result.terminal, false);
});
test("unclear or divergent checks keep history without granting next-step guidance", () => {
  for (const assessment of ["unclear", "possible_divergence"]) {
    const result = taskCheckpoint(model, [check("joined"), check("unknown", assessment), check("unknown", assessment)]);
    assert.equal(result.state.id, "joined");
    assert.equal(result.current, undefined);
    assert.equal(result.nextAction, undefined);
    assert.equal(result.terminal, false);
  }
});
test("unknown matching IDs cannot seed guidance", () => {
  const result = taskCheckpoint(model, [check("invented")]);
  assert.equal(result.lastMatch, undefined);
  assert.equal(result.nextAction, undefined);
});
test("pending and failed checks cannot reuse stale guidance", () => {
  const result = taskCheckpoint(model, [check("joined")], true);
  assert.equal(result.state.id, "joined");
  assert.equal(result.current, undefined);
  assert.equal(result.nextAction, undefined);
});
test("branching states require user review rather than selecting the first action", () => {
  const branch = { ...model, actions: [...model.actions, { id: "other", fromState: "joined", toState: "start" }] };
  assert.equal(taskCheckpoint(branch, [check("joined")]).ambiguous, true);
  assert.equal(taskCheckpoint(branch, [check("joined")]).nextAction, undefined);
});
test("only a declared matched state with an incoming transition can be terminal", () => {
  assert.equal(taskCheckpoint(model, [check("done")]).terminal, true);
  assert.equal(taskCheckpoint({ ...model, states: [...model.states, { id: "isolated" }] }, [check("isolated")]).terminal, false);
  assert.equal(taskCheckpoint(model, []).terminal, false);
});
