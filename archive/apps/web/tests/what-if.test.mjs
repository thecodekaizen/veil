import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function loadTypeScript(relativePath) {
  const source = await readFile(new URL(relativePath, import.meta.url), "utf8");
  const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);
}

const [{ interpretWhatIf }, { SAMPLE_SKILL }] = await Promise.all([
  loadTypeScript("../lib/what-if.ts"),
  loadTypeScript("../lib/skill-model.ts"),
]);
const originalOrder = SAMPLE_SKILL.actions.map((action) => action.id);

test("previews an action moved before a named action without mutating the current order", () => {
  const result = interpretWhatIf(SAMPLE_SKILL, originalOrder, "What if I mount support bracket before place spacer ring?");
  assert.equal(result.ok, true);
  assert.deepEqual(result.actionIds, ["place-bracket", "place-washer", "insert-bolt"]);
  assert.deepEqual(originalOrder, ["place-washer", "place-bracket", "insert-bolt"]);
});

test("supports moving a named action to the start", () => {
  const result = interpretWhatIf(SAMPLE_SKILL, originalOrder, "Mount support bracket first");
  assert.equal(result.ok, true);
  assert.equal(result.actionIds[0], "place-bracket");
});

test("asks for clarification when an action cannot be matched", () => {
  const result = interpretWhatIf(SAMPLE_SKILL, originalOrder, "Put the mystery part before the spacer ring");
  assert.equal(result.ok, false);
  assert.match(result.message, /couldn't match|which action/i);
});

test("rejects moving an action relative to itself", () => {
  const result = interpretWhatIf(SAMPLE_SKILL, originalOrder, "Place spacer ring before Place spacer ring");
  assert.equal(result.ok, false);
  assert.match(result.message, /cannot be reordered/i);
});

test("matches an action through any of its involved parts", () => {
  const multiPartSkill = {
    ...SAMPLE_SKILL,
    objects: [...SAMPLE_SKILL.objects, { id: "lock-nut", name: "Lock nut", color: "stone", shape: "component" }],
    actions: SAMPLE_SKILL.actions.map((action) => action.id === "place-bracket" ? { ...action, objectIds: ["bracket", "lock-nut"] } : action),
  };
  const result = interpretWhatIf(multiPartSkill, originalOrder, "Mount lock nut after the fastener");
  assert.equal(result.ok, true);
  assert.deepEqual(result.actionIds, ["place-washer", "insert-bolt", "place-bracket"]);
});
