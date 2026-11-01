"""Eval: baseline-only vs baseline+Spark coverage of the synthetic fixture's known targets.

Ground truth (veil/artifacts/smoke-001/ground-truth.json) is read here only, never by inference.
Usage: uv run --project veil python -m eval.run_eval dev RUN_DIR OUT_DIR       (synthetic fixture = DEV set)
       uv run --project veil python -m eval.run_eval heldout LABELS_DIR OUT_DIR  (gate clips c1..cN = HELD-OUT set)
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


def dev(run: Path, out: Path):
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
    (out / 'dev_results.json').write_text(json.dumps(result, indent=1) + '\n')
    lines = ['# Eval (DEV set): baseline-only vs baseline+Spark, synthetic clip, development check', '',
             '| target | frames | baseline-only mean cover | baseline+Spark mean cover | baseline-only frames >=90% | baseline+Spark frames >=90% |',
             '| --- | --- | --- | --- | --- | --- |']
    for k, v in result['targets'].items():
        b, s2 = v['baseline_only'], v['baseline_plus_spark']
        lines.append(f"| {k} | {b['frames']} | {b['mean_coverage']:.2f} | {s2['mean_coverage']:.2f} | {b['frames_covered_pct']}% | {s2['frames_covered_pct']}% |")
    a = result['audio']
    lines += ['', f"Audio: spoken span {s}-{e}s, muted {a['muted_intervals_s']}, span covered {a['span_covered_pct']}%, "
                  f"over-cover {a['over_cover_s']} s, detected digits {a['detected_digits']} (true {a['true_digits']}), window precision.",
              '', '## Caveats'] + [f'- {c}' for c in result['caveats']]
    (out / 'dev_results.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


def heldout(labels_dir: Path, out: Path, runs: Path = Path('runs')):
    """Per labelled visual leak: matched by a baseline-only vs a baseline+Spark concept (mask IoU >= 0.5 at a ref_box), and
    mask coverage of the matched concept inside visible_ranges. Audio is Veil-only. Reads labels (eval-only) and run artifacts."""
    from gate.labels_schema import Labels
    from gate.score_gate import best_match, score_audio, track_coverage
    from veil.schemas import DiscoverArtifact, KeyframeArtifact, ListenArtifact, TrackArtifact
    files = sorted(labels_dir.glob('*.json'))
    if not files:
        out.mkdir(parents=True, exist_ok=True)
        (out / 'heldout_results.md').write_text('# Eval (HELD-OUT set): NOT RUN\n\nNo label files in %s.\n' % labels_dir)
        print('held-out eval NOT RUN: no labels')
        return
    rows, audio = [], []
    for f in files:
        lab = Labels.model_validate_json(f.read_text())
        root = runs / lab.clip_id
        kf = KeyframeArtifact.model_validate_json((root / 'keyframes.json').read_text())
        disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
        track = TrackArtifact.model_validate_json((root / 'track_final.json').read_text())
        listen = ListenArtifact.model_validate_json((root / 'listen.json').read_text())
        src = {c.concept_id: c.source for c in disc.concepts}
        for leak in lab.leaks:
            if leak.kind == 'audio':
                audio.append({'clip': lab.clip_id, **score_audio(leak, listen)})
                continue
            row = {'clip': lab.clip_id, 'leak_id': leak.leak_id, 'concept': leak.concept, 'in_baseline': leak.in_baseline}
            for name, srcs in (('baseline_only', {'baseline'}), ('baseline_plus_spark', {'baseline', 'spark'})):
                m = best_match(track, src, srcs, leak.ref_boxes, lab.fps, kf.width, kf.height)
                row[name] = {'matched': m['matched'], 'iou': m['iou'], 'concept_id': m['concept_id'],
                             'mask_pct': track_coverage(track, set(m['matched_concepts']), leak.visible_ranges, lab.fps)['mask_pct'] if m['matched'] else 0.0}
            rows.append(row)
    res = {'set': 'held-out (gate clips)', 'leaks': rows, 'audio': audio}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'heldout_results.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    L = ['# Eval (HELD-OUT set): baseline-only vs baseline+Spark', '',
         '| clip | leak | in_baseline | baseline-only (IoU / frames with mask) | baseline+Spark (IoU / frames with mask) |', '| --- | --- | --- | --- | --- |']
    for r in rows:
        b, s2 = r['baseline_only'], r['baseline_plus_spark']
        L.append(f"| {r['clip']} | {r['leak_id']} {r['concept']} | {r['in_baseline']} | "
                 f"{'matched' if b['matched'] else 'no'} {b['iou']} / {b['mask_pct']}% | {'matched' if s2['matched'] else 'no'} {s2['iou']} / {s2['mask_pct']}% |")
    nb, ns = sum(r['baseline_only']['matched'] for r in rows), sum(r['baseline_plus_spark']['matched'] for r in rows)
    L += ['', f'Matched visual leaks: baseline-only {nb}/{len(rows)}, baseline+Spark {ns}/{len(rows)}.']
    for a in audio:
        L.append(f"Audio {a['clip']}/{a['leak_id']}: detected={a.get('detected_digits')} exact={a.get('exact')} edit={a.get('edit_distance')}, "
                 f"coverage {a['coverage_pct']}%, over-cover {a['over_cover_s']} s ({a['precision_method']}); baseline has no audio component.")
    (out / 'heldout_results.md').write_text('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == 'dev':
        dev(Path(args[0]), Path(args[1]))
    elif mode == 'heldout':
        heldout(Path(args[0]), Path(args[1]))
    else:
        sys.exit('mode must be dev or heldout')
