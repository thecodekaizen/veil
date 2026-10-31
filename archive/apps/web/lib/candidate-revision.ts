export type CandidateRevision = {
  id: string;
  timestamp: string;
  targetType: "object" | "action";
  targetId: string;
  field: "label" | "action";
  originalValue: string;
  revisedValue: string;
};

export type EditableProcess = {
  objects: { id: string; label: string; visual_description: string }[];
  transitions: { id: string; action: string; [key: string]: unknown }[];
  [key: string]: unknown;
};

/**
 * Record a human correction to an object label or action name during candidate review.
 * Preserves audit history so reviewers can see what was proposed vs what was corrected.
 */
export function applyRevision<T extends EditableProcess>(
  process: T,
  revisions: CandidateRevision[],
  targetType: "object" | "action",
  targetId: string,
  revisedValue: string,
  timestamp = new Date().toISOString(),
): { process: T; revisions: CandidateRevision[]; applied: boolean } {
  const trimmed = revisedValue.trim();
  if (!trimmed) {
    return { process, revisions, applied: false };
  }

  if (targetType === "object") {
    const obj = process.objects.find((o) => o.id === targetId);
    if (!obj || obj.label === trimmed) {
      return { process, revisions, applied: false };
    }
    const revision: CandidateRevision = {
      id: `rev-obj-${targetId}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp,
      targetType: "object",
      targetId,
      field: "label",
      originalValue: obj.label,
      revisedValue: trimmed,
    };
    const nextProcess = {
      ...process,
      objects: process.objects.map((o) => (o.id === targetId ? { ...o, label: trimmed } : o)),
    };
    return { process: nextProcess, revisions: [...revisions, revision], applied: true };
  } else {
    const tr = process.transitions.find((t) => t.id === targetId);
    if (!tr || tr.action === trimmed) {
      return { process, revisions, applied: false };
    }
    const revision: CandidateRevision = {
      id: `rev-act-${targetId}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp,
      targetType: "action",
      targetId,
      field: "action",
      originalValue: tr.action,
      revisedValue: trimmed,
    };
    const nextProcess = {
      ...process,
      transitions: process.transitions.map((t) => (t.id === targetId ? { ...t, action: trimmed } : t)),
    };
    return { process: nextProcess, revisions: [...revisions, revision], applied: true };
  }
}

/**
 * Revert a specific revision, restoring its original value and removing it from the revision trail.
 */
export function revertRevision<T extends EditableProcess>(
  process: T,
  revisions: CandidateRevision[],
  revisionId: string,
): { process: T; revisions: CandidateRevision[]; reverted: boolean } {
  const rev = revisions.find((r) => r.id === revisionId);
  if (!rev) {
    return { process, revisions, reverted: false };
  }

  let nextProcess = process;
  if (rev.targetType === "object") {
    nextProcess = {
      ...process,
      objects: process.objects.map((o) => (o.id === rev.targetId ? { ...o, label: rev.originalValue } : o)),
    };
  } else {
    nextProcess = {
      ...process,
      transitions: process.transitions.map((t) => (t.id === rev.targetId ? { ...t, action: rev.originalValue } : t)),
    };
  }

  const nextRevisions = revisions.filter((r) => r.id !== revisionId);
  return { process: nextProcess, revisions: nextRevisions, reverted: true };
}
