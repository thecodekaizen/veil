import type { SkillModel } from "./skill-model";

type Check = {
  checkedAt: string;
  observation: { assessment: string; state_id: string };
};

/** Derive guidance from a matched state, never from simulated progress or elapsed time. */
export function taskCheckpoint(model: SkillModel, checks: readonly Check[], unavailable = false) {
  const declared = new Set(model.states?.map((state) => state.id) ?? []);
  const known = (check: Check) => check.observation.assessment === "consistent"
    && declared.has(check.observation.state_id);
  const latest = checks.at(-1);
  const lastMatch = [...checks].reverse().find(known);
  const current = !unavailable && latest && known(latest) ? latest : undefined;
  const state = lastMatch && model.states?.find((item) => item.id === lastMatch.observation.state_id);
  const next = current ? model.actions.filter((action) => action.fromState === current.observation.state_id) : [];
  const terminal = Boolean(current && next.length === 0
    && model.actions.some((action) => action.toState === current.observation.state_id));
  return { lastMatch, state, current, nextAction: next.length === 1 ? next[0] : undefined,
    ambiguous: next.length > 1, terminal };
}
