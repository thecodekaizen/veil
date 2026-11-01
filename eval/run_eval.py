"""Eval: baseline-only vs baseline+Spark coverage of the synthetic fixture's known targets.

Ground truth (veil/artifacts/smoke-001/ground-truth.json) is read here only, never by inference.
Usage: uv run --project veil python eval/run_eval.py RUN_DIR OUT_DIR
Coverage of a target in a frame = fraction of the ground-truth box covered by the union of applied cover boxes
(redact.json) from the chosen concept sources. A target counts as covered in a frame at >= 0.9.
"""
import json
import sys
from pathlib import Path

import numpy as np

GT = Path('veil/artifacts/smoke-001/ground-truth.json')
FRAME_COVER = 0.9


def coverage(gt_box, boxes, w=1280, h=720) -> float:
    x1, y1, x2, y2 = map(int, gt_box)
    m = np.zeros((max(1, y2 - y1), max(1, x2 - x1)), bool)
    for bx1, by1, bx2, by2 in boxes:
        m[max(0, by1 - y1):max(0, by2 - y1), max(0, bx1 - x1):max(0, bx2 - x1)] = True
    return float(m.mean())


def main(run: Path, out: Path):
    gt = json.loads(GT.read_text())
    red = json.loads((run / 'redact.json').read_text())
    listen = json.loads((run / 'listen.json').read_text())
    by_src = {'baseline_only': {'baseline'}, 'baseline_plus_spark': {'baseline', 'spark'}}
    boxes = {}  # source set -> frame -> boxes
    for name, srcs in by_src.items():
        d = {}
        for r in red['regions']:
            if r['source'] in srcs:
                for f in r['frames']:
                    d.setdefault(f['frame_idx'], []).append(f['box'])
        boxes[name] = d
    result = {'clip': 'veil/artifacts/smoke-001/input.mp4 (synthetic, English, 1 clip)', 'frame_cover_threshold': FRAME_COVER,
              'targets': {}, 'audio': {}, 'caveats': [
                  'One synthetic clip; targets are rendered panels, not real footage. This is a development check, not the preregistered gate (gate NOT RUN).',
                  'face_source_panel is the whole rendered portrait panel; the models cover the face inside it, so ~0.39 cover is a ground-truth-definition effect, not a measured miss of the face.',
                  'The concept set was developed while looking at this clip; numbers are not held-out evidence.']}
    for key in ('face_source_panel', 'plate', 'printed_phone'):
        frames = [f for f in gt['frames'] if f.get(key)]
        for name in by_src:
            covs = [coverage(f[key], boxes[name].get(f['frame'], [])) for f in frames]
            result['targets'].setdefault(key, {})[name] = {
                'frames': len(frames), 'mean_coverage': round(float(np.mean(covs)), 4),
                'frames_covered_pct': round(100 * float(np.mean([c >= FRAME_COVER for c in covs])), 1)}
    # Number span: onset from model-free energy segmentation (docs/api_notes.md), end from the fixture; same reference
    # as docs/decisions.md. The fixture's speech_start_ms covers the whole sentence, not just the number.
    s, e = 4.9, gt['speech_end_ms'] / 1000
    muted = [tuple(m) for m in red['muted_intervals']]
    cov = sum(max(0, min(e, b) - max(s, a)) for a, b in muted) / (e - s)
    over = sum(b - a for a, b in muted) - sum(max(0, min(e, b) - max(s, a)) for a, b in muted)
    result['audio'] = {'spoken_span_s': [s, e], 'muted_intervals_s': muted, 'span_covered_pct': round(100 * cov, 1),
                       'over_cover_s': round(over, 2), 'detected_digits': [p['normalized_value'] for p in listen['pii']],
                       'true_digits': '2025550146', 'precision': 'window',
                       'reference': 'number span: onset 4.9 s energy-based, end from fixture speech_end_ms', 'note': 'baseline has no audio component; audio is Veil-only'}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'results.json').write_text(json.dumps(result, indent=1) + '\n')
    lines = ['# Eval: baseline-only vs baseline+Spark (synthetic clip, development check)', '',
             '| target | frames | baseline-only mean cover | baseline+Spark mean cover | baseline-only frames >=90% | baseline+Spark frames >=90% |',
             '| --- | --- | --- | --- | --- | --- |']
    for k, v in result['targets'].items():
        b, s2 = v['baseline_only'], v['baseline_plus_spark']
        lines.append(f"| {k} | {b['frames']} | {b['mean_coverage']:.2f} | {s2['mean_coverage']:.2f} | {b['frames_covered_pct']}% | {s2['frames_covered_pct']}% |")
    a = result['audio']
    lines += ['', f"Audio: spoken span {s}-{e}s, muted {a['muted_intervals_s']}, span covered {a['span_covered_pct']}%, "
                  f"over-cover {a['over_cover_s']} s, detected digits {a['detected_digits']} (true {a['true_digits']}), window precision.",
              '', '## Caveats'] + [f'- {c}' for c in result['caveats']]
    (out / 'results.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
