export type Status = 'COVERED' | 'UNRESOLVED' | 'NOT_CHECKED';
export interface Region { concept_id: string; label: string; source: 'spark' | 'baseline'; why: string; frames: number[][] }
export interface Finding { finding_id: string; kind: string; label: string; source: string; status: Status; reasons: string[] }
export interface Check { check_id: string; description: string; status: 'RAN' | 'NOT_CHECKED'; detail: string }
export interface Manifest {
  run_id: string; provenance: string; footer: string;
  video: { fps: number; frames: number; width: number; height: number; duration_s: number };
  regions: Region[]; findings: Finding[]; checks: Check[]; concepts_without_masks: string[]; limitations: string[];
  audio: { transcript: string; method: string; window_s: number; bleep_pad_s: number; muted_intervals: number[][];
           pii: { digits: string; t_start: number; t_end: number; precision: string }[] };
  cost: { calls: number; failed: number; estimated_usd: number };
  models: Record<string, string>;
}
