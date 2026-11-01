import { useEffect, useState } from 'react';
import type { Manifest } from '../demo/types';

export type { Manifest };
export type Gate = { label: string; verdict: string } & Record<'G1' | 'G2' | 'G3' | 'G4a' | 'G4b', { ok: boolean; value: string }>;
export type Results = {
  heldout: { baseline_only: string; with_spark: string; source: string };
  gates: Record<string, Gate>;
  models: { model: string; calls: number; failed: number; median_latency_s: number | null; p90_latency_s: number | null; est_usd: number }[];
  usd_per_clip_run: { mean: number; min: number; max: number } | null;
  clip_runs: number;
  tests: number;
};

export const BASE = import.meta.env.BASE_URL;
export const REPO = 'https://github.com/thecodekaizen/veil';

/** Runs shipped with the site: real pipeline outputs exported by `veil export-web`. */
export const RUNS = [
  { id: 'c2', title: 'Street clip', kind: 'Visual leaks', blurb: 'A delivery notification with a full name and a door plate with a surname and flat number.' },
  { id: 'c3', title: 'Spoken number', kind: 'Audio leak', blurb: 'A phone number read out in Hindi over street footage, with a book cover as a harmless control.' },
] as const;

type Load<T> = { data: T | null; error: string | null };

function useJson<T>(url: string | null): Load<T> {
  const [s, set] = useState<Load<T>>({ data: null, error: null });
  useEffect(() => {
    if (!url) return;
    let live = true;
    set({ data: null, error: null });
    fetch(url)
      .then(r => { if (!r.ok) throw new Error(`${r.status} ${r.statusText}`); return r.json(); })
      .then(d => live && set({ data: d, error: null }))
      .catch(e => live && set({ data: null, error: String(e.message || e) }));
    return () => { live = false; };
  }, [url]);
  return s;
}

export const useManifest = (run: string) => useJson<Manifest>(`${BASE}demo/${run}/manifest.json`);
export const useResults = () => useJson<Results>(`${BASE}data/results.json`);
export type ExportFile = 'output.mp4' | 'output_natural.mp4';
export const media = (run: string, file: 'input.mp4' | ExportFile) => `${BASE}demo/${run}/${file}`;

/** Region boxes present at a given frame. */
export function regionsAt(m: Manifest, frame: number) {
  const out: { box: number[]; label: string; source: string; concept: string }[] = [];
  for (const r of m.regions) {
    for (const [f, ...box] of r.frames) {
      if (f === frame) { out.push({ box, label: r.label, source: r.source, concept: r.concept_id }); break; }
    }
  }
  return out;
}

export const prettyConcept = (s: string) => s.replace(/^(spark|baseline)-/, '').replace(/-/g, ' ');
