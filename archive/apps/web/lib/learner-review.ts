/** Select recovery evidence without treating unrelated progress as a repair. */
type ReviewEvent = {
  time_seconds: number;
  state_id: string;
  assessment: string;
  object_ids: string[];
};
type Difference = { time_seconds: number; object_ids: string[] };

export function findRecoveryEvent<T extends ReviewEvent>(
  events: T[], differences: Difference[], declaredStates: readonly string[],
): T | undefined {
  if (!differences.length) return undefined;
  const lastDivergence = Math.max(
    ...differences.map((item) => item.time_seconds),
    ...events.filter((item) => item.assessment === "divergent").map((item) => item.time_seconds),
  );
  const states = new Set(declaredStates);
  let completion: T | undefined;
  for (const difference of differences) {
    const affected = Array.isArray(difference.object_ids)
      ? difference.object_ids.filter((id) => id !== "unknown") : [];
    if (!affected.length) return undefined;
    const match = events.find((event) =>
      event.assessment === "consistent" && states.has(event.state_id)
      && event.time_seconds > lastDivergence
      && Array.isArray(event.object_ids)
      && affected.every((id) => event.object_ids.includes(id)),
    );
    if (!match) return undefined;
    if (!completion || match.time_seconds > completion.time_seconds) completion = match;
  }
  return completion;
}
