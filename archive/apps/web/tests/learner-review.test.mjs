import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../lib/learner-review.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { findRecoveryEvent } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);
const event = (time, ids, assessment = "consistent", state_id = "assembled") => ({ time_seconds: time, object_ids: ids, assessment, state_id });
const difference = (time, ids = ["panel"]) => ({ time_seconds: time, object_ids: ids });
const states = ["assembled"];

test("selects the later matching event for affected parts", () => {
  const recovery = event(22, ["panel", "core"]);
  assert.equal(findRecoveryEvent([event(3, ["panel"]), recovery], [difference(14)], states), recovery);
});
test("does not use unrelated object progress as recovery", () => {
  assert.equal(findRecoveryEvent([event(22, ["core"])], [difference(14)], states), undefined);
});
test("does not use recovery before the last reported difference", () => {
  assert.equal(findRecoveryEvent([event(22, ["panel"])], [difference(14), difference(25)], states), undefined);
});
test("a later divergent event also invalidates earlier recovery", () => {
  assert.equal(findRecoveryEvent([event(22, ["panel"]), event(25, ["panel"], "divergent")], [difference(14)], states), undefined);
});
test("requires a known affected part and a declared matching state", () => {
  assert.equal(findRecoveryEvent([event(22, ["panel"])], [difference(14, ["unknown"])], states), undefined);
  assert.equal(findRecoveryEvent([event(22, ["panel"], "consistent", "invented")], [difference(14)], states), undefined);
  assert.equal(findRecoveryEvent([event(22, ["panel"])], [], states), undefined);
});
test("every reported issue must have later matching evidence", () => {
  const differences = [difference(10), difference(14, ["core"])];
  assert.equal(findRecoveryEvent([event(22, ["panel"])], differences, states), undefined);
  const final = event(24, ["core"]);
  assert.equal(findRecoveryEvent([event(22, ["panel"]), final], differences, states), final);
});
