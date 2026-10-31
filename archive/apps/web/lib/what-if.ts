import type { SkillModel } from "./skill-model";

export type WhatIfInterpretation =
  | { ok: true; actionIds: string[]; summary: string }
  | { ok: false; message: string };

const STOP_WORDS = new Set([
  "a", "an", "and", "at", "before", "after", "anything", "else", "first", "for",
  "happen", "happens", "how", "i", "if", "in", "instead", "it", "me", "of", "on",
  "or", "the", "then", "this", "to", "what", "when", "would", "you",
]);

function normalize(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function tokens(value: string) {
  return normalize(value).split(/\s+/).filter((token) => token && !STOP_WORDS.has(token));
}

function resolveAction(model: SkillModel, phrase: string) {
  const query = tokens(phrase);
  if (query.length === 0) return { kind: "none" as const };
  const matches = model.actions.map((action) => {
    const objects = model.objects.filter((item) => action.objectIds.includes(item.id));
    const aliases = [action.label, ...objects.flatMap((object) => [object.name, object.visualDescription ?? ""])];
    const aliasTokens = new Set(aliases.flatMap(tokens));
    const overlap = query.filter((token) => aliasTokens.has(token)).length;
    const exactPhrase = aliases.some((alias) => {
      const normalizedAlias = normalize(alias);
      return normalizedAlias.length > 0 && normalize(phrase).includes(normalizedAlias);
    });
    return { action, score: overlap * 4 + (exactPhrase ? 20 : 0) + overlap / query.length };
  }).filter((item) => item.score > 0).sort((left, right) => right.score - left.score);

  if (matches.length === 0) return { kind: "none" as const };
  if (matches[1] && Math.abs(matches[0].score - matches[1].score) < 0.01) {
    return { kind: "ambiguous" as const, labels: matches.filter((item) => Math.abs(matches[0].score - item.score) < 0.01).map((item) => item.action.label) };
  }
  return { kind: "matched" as const, action: matches[0].action };
}

function insertRelative(order: string[], targetId: string, anchorId: string, relation: "before" | "after") {
  if (targetId === anchorId || !order.includes(targetId) || !order.includes(anchorId)) return null;
  const next = order.filter((id) => id !== targetId);
  const anchorIndex = next.indexOf(anchorId);
  if (anchorIndex < 0) return null;
  next.splice(anchorIndex + (relation === "after" ? 1 : 0), 0, targetId);
  return next;
}

/** Interpret a bounded ordering question; never runs the simulation itself. */
export function interpretWhatIf(model: SkillModel, currentOrder: string[], prompt: string): WhatIfInterpretation {
  const text = normalize(prompt);
  if (!text) return { ok: false, message: "Describe an action and where you want it to happen." };

  const relation = text.match(/\b(before|ahead of|in front of|after|following)\b/);
  if (relation?.index !== undefined) {
    const left = text.slice(0, relation.index).replace(/^(what if|if|i|we|you|would|do|did|move|try)\s+/g, "");
    const right = text.slice(relation.index + relation[0].length);
    const target = resolveAction(model, left);
    const anchor = resolveAction(model, right);
    if (target.kind === "ambiguous") return { ok: false, message: `Which action did you mean: ${target.labels.join(" or ")}?` };
    if (anchor.kind === "ambiguous") return { ok: false, message: `Which action should it be relative to: ${anchor.labels.join(" or ")}?` };
    if (target.kind !== "matched" || anchor.kind !== "matched") return { ok: false, message: "I couldn't match both actions. Use the action names shown in the Skill Model." };
    const direction = relation[1] === "after" || relation[1] === "following" ? "after" : "before";
    const actionIds = insertRelative(currentOrder, target.action.id, anchor.action.id, direction);
    if (!actionIds) return { ok: false, message: "Those actions cannot be reordered in the current proposal." };
    return { ok: true, actionIds, summary: `Move “${target.action.label}” ${direction} “${anchor.action.label}”.` };
  }

  if (/\b(first|at the start|before anything else)\b/.test(text)) {
    const targetText = text.replace(/\b(first|at the start|before anything else)\b/g, " ").replace(/^(what if|if|i|we|you|would|do|did|move|try)\s+/g, "");
    const target = resolveAction(model, targetText);
    if (target.kind === "ambiguous") return { ok: false, message: `Which action do you want first: ${target.labels.join(" or ")}?` };
    if (target.kind !== "matched") return { ok: false, message: "I couldn't match that action. Use an action name shown in the Skill Model." };
    const actionIds = [target.action.id, ...currentOrder.filter((id) => id !== target.action.id)];
    return { ok: true, actionIds, summary: `Move “${target.action.label}” to the beginning.` };
  }

  return { ok: false, message: "For now, ask what happens if an action comes first, before another action, or after another action." };
}
