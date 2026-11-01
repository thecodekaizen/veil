"""Score the preregistered gate (gate/GATE.md) from labels and run artifacts.

Usage: uv run --project veil python -m gate.score_gate [--labels gate/labels] [--runs runs] [--clips gate/clips] [--out gate]
Reads gate/labels/<clip_id>.json and runs/<clip_id>/{keyframes,discover,track_final,listen,redact,audit}.json.
Writes OUT/GATE_RESULT.md and OUT/gate_result.json. With no label files it writes "GATE: NOT RUN" and exits 2.
Thresholds come from GATE.md and are not parameters. Interpretations the text leaves open are listed under `notes`.
Ground truth (labels) is read here only; it never enters inference.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

from gate.labels_schema import Labels
from veil.overlay import decode_mask
from veil.schemas import (AuditArtifact, DiscoverArtifact, KeyframeArtifact, ListenArtifact, MaskFrame,
                          RedactArtifact, TrackArtifact)

IOU_MIN, FRAME_TOL, TRACK_MIN, OVER_COVER_MAX_S = 0.5, 2, 0.95, 2.5
EXPECTED_BLEEP_PAD_S = 0.5  # docs/decisions.md
NOTES = [
    'G1/G2 IoU uses the SAM mask pixels (not its bbox) against the labelled ref_box; frames without a mask (held/padded) never count.',
    'A leak/control counts as matched if ANY of its ref_boxes is matched by a concept at that ref_box time (+/-2 frames).',
    'G1 aggregates visual leaks across all label files and expects exactly 4 planted visual leaks.',
    'G3 (gate decision) counts frames with a real SAM mask of ANY Spark concept that matches the leak (IoU>=0.5 at a ref_box) inside visible_ranges; coverage including held/padded frames is reported next to it.',
    'G4a takes the PII hit overlapping the labelled audio span (else the hit nearest to it); digit accuracy is reported, not gated.',
    'G5 is reported, not a kill criterion: PASS if the audit has no UNRESOLVED finding; otherwise the findings are listed.',
]


def frame_of(t_s: float, fps: float) -> int:
    return int(round(t_s * fps))


def mask_iou(mf: MaskFrame, box: tuple[float, float, float, float], width: int, height: int) -> float:
    """IoU between the SAM mask pixels and an xyxy box, both in source pixels. 0.0 if the frame has no mask."""
    if mf.mask is None:
        return 0.0
    full = np.zeros((height, width), bool)
    bits = decode_mask(mf.mask) > 0
    l, t = int(round(mf.mask.bounds[0])), int(round(mf.mask.bounds[1]))
    y0, x0 = max(0, t), max(0, l)
    y1, x1 = min(height, t + bits.shape[0]), min(width, l + bits.shape[1])
    if y1 > y0 and x1 > x0:
        full[y0:y1, x0:x1] = bits[y0 - t:y1 - t, x0 - l:x1 - l]
    bx = np.zeros_like(full)
    bx[max(0, int(box[1])):min(height, int(math.ceil(box[3]))), max(0, int(box[0])):min(width, int(math.ceil(box[2])))] = True
    inter, union = int((full & bx).sum()), int((full | bx).sum())
    return inter / union if union else 0.0


def best_match(track: TrackArtifact, concept_sources: dict[str, str], source: set[str], ref_boxes, fps, width, height):
    """Best IoU over concepts whose source is in `source`, over all ref_boxes and frames within +/-2. Returns dict."""
    best = {'iou': 0.0, 'concept_id': None, 'ref_t_s': None, 'frame': None}
    per_concept: dict[str, float] = {}
    for m in track.masklets:
        if concept_sources.get(m.concept_id) not in source:
            continue
        by = {f.frame_idx: f for f in m.frames}
        for rb in ref_boxes:
            c = frame_of(rb.t_s, fps)
            for fi in range(c - FRAME_TOL, c + FRAME_TOL + 1):
                if fi in by:
                    iou = mask_iou(by[fi], (rb.x, rb.y, rb.x + rb.w, rb.y + rb.h), width, height)
                    per_concept[m.concept_id] = max(per_concept.get(m.concept_id, 0.0), iou)
                    if iou > best['iou']:
                        best = {'iou': round(iou, 3), 'concept_id': m.concept_id, 'ref_t_s': rb.t_s, 'frame': fi}
    best['matched'] = best['iou'] >= IOU_MIN
    best['matched_concepts'] = sorted(c for c, v in per_concept.items() if v >= IOU_MIN)
    return best


def range_frames(ranges, fps) -> list[int]:
    out = set()
    for a, b in ranges:
        out.update(range(int(math.ceil(a * fps - 1e-9)), int(math.floor(b * fps + 1e-9)) + 1))
    return sorted(out)


def track_coverage(track: TrackArtifact, concept_ids: set[str], ranges, fps) -> dict:
    frames = range_frames(ranges, fps)
    real, applied = set(), set()
    for m in track.masklets:
        if m.concept_id in concept_ids:
            for f in m.frames:
                applied.add(f.frame_idx)
                if f.mask is not None:
                    real.add(f.frame_idx)
    n = max(1, len(frames))
    return {'frames_in_ranges': len(frames), 'mask_pct': round(100 * sum(i in real for i in frames) / n, 1),
            'with_held_pct': round(100 * sum(i in applied for i in frames) / n, 1)}


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def score_audio(leak, listen: ListenArtifact) -> dict:
    a = leak.audio
    out = {'leak_id': leak.leak_id, 'label_span_s': [a.t_start, a.t_end], 'precision_method': listen.method,
           'pii_precision': sorted({p.precision for p in listen.pii}), 'bleep_pad_s': listen.bleep_pad_s,
           'bleep_intervals': [list(b) for b in listen.bleep_intervals]}
    hits = sorted(listen.pii, key=lambda p: (not (p.t_start < a.t_end and p.t_end > a.t_start),
                                             abs((p.t_start + p.t_end) / 2 - (a.t_start + a.t_end) / 2)))
    out['g4a_detected'] = bool(hits)
    if hits:
        d = hits[0].normalized_value
        out.update(detected_digits=d, exact=d == a.digits, edit_distance=edit_distance(d, a.digits),
                   mobile_pattern=hits[0].mobile_pattern, pii_span_s=[hits[0].t_start, hits[0].t_end])
    covered = sum(max(0.0, min(a.t_end, e) - max(a.t_start, s)) for s, e in listen.bleep_intervals)
    total = sum(e - s for s, e in listen.bleep_intervals)
    cov_pct = 100 * covered / (a.t_end - a.t_start)
    over = total - covered
    out.update(coverage_pct=round(cov_pct, 1), over_cover_s=round(over, 2),
               g4b_ok=cov_pct >= 100 - 1e-6 and over <= OVER_COVER_MAX_S + 1e-9)
    return out


def verdict_of(g: dict) -> str:
    return 'PASS' if all(g[k]['ok'] for k in ('G1', 'G2', 'G3', 'G4a', 'G4b')) else 'FAIL'


def score(labels_dir: Path, runs: Path, clips: Path) -> dict:
    files = sorted(labels_dir.glob('*.json'))
    if not files:
        return {'verdict': 'NOT RUN', 'reason': f'no label files in {labels_dir}', 'notes': NOTES}
    per_clip, visual, controls, audio = {}, [], [], []
    problems = []
    for f in files:
        labels = Labels.model_validate_json(f.read_text())
        cid, root = labels.clip_id, runs / labels.clip_id
        clip = clips / f'{cid}.mp4'
        if not clip.exists() or hashlib.sha256(clip.read_bytes()).hexdigest() != labels.clip_sha256:
            problems.append(f'{cid}: clip missing or sha256 does not match labels; aborting (GATE.md measurement notes)')
            continue
        need = ['keyframes', 'discover', 'track_final', 'listen', 'redact', 'audit']
        missing = [n for n in need if not (root / f'{n}.json').exists()]
        if missing:
            problems.append(f'{cid}: missing run artifacts {missing}')
            continue
        kf = KeyframeArtifact.model_validate_json((root / 'keyframes.json').read_text())
        disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
        track = TrackArtifact.model_validate_json((root / 'track_final.json').read_text())
        listen = ListenArtifact.model_validate_json((root / 'listen.json').read_text())
        audit = AuditArtifact.model_validate_json((root / 'audit.json').read_text())
        sources = {c.concept_id: c.source for c in disc.concepts}
        paths = {'run': str(root), 'track': str(root / 'track_final.json'), 'listen': str(root / 'listen.json')}
        per_clip[cid] = {'paths': paths, 'audit_unresolved': [x.finding_id for x in audit.findings if x.status == 'UNRESOLVED']}
        for leak in labels.leaks:
            if leak.kind == 'visual':
                m = best_match(track, sources, {'spark'}, leak.ref_boxes, labels.fps, kf.width, kf.height)
                row = {'clip': cid, 'leak_id': leak.leak_id, 'concept': leak.concept, 'in_baseline': leak.in_baseline, **m,
                       'matched_prompt': next((c.sam_prompt for c in disc.concepts if c.concept_id == m['concept_id']), None)}
                if m['matched']:
                    row['g3'] = track_coverage(track, set(m['matched_concepts']), leak.visible_ranges, labels.fps)
                visual.append(row)
            else:
                audio.append({'clip': cid, **score_audio(leak, listen), 'paths': paths})
        for c in labels.safe_controls:
            m = best_match(track, sources, {'spark'}, c.ref_boxes, labels.fps, kf.width, kf.height)
            controls.append({'clip': cid, 'control_id': c.control_id, 'description': c.description, **m,
                             'matched_prompt': next((x.sam_prompt for x in disc.concepts if x.concept_id == m['concept_id']), None)})
        if abs(listen.bleep_pad_s - EXPECTED_BLEEP_PAD_S) > 1e-9:
            problems.append(f'{cid}: bleep pad {listen.bleep_pad_s} differs from the value recorded in docs/decisions.md')
    if problems:
        return {'verdict': 'NOT RUN', 'reason': '; '.join(problems), 'notes': NOTES}
    covered = [v for v in visual if v['matched']]
    g = {
        'G1': {'covered': len(covered), 'planted': len(visual), 'covered_not_in_baseline': sum(not v['in_baseline'] for v in covered),
               'ok': len(visual) == 4 and len(covered) >= 3 and any(not v['in_baseline'] for v in covered), 'rows': visual},
        'G2': {'controls_matched': sum(c['matched'] for c in controls), 'controls': len(controls),
               'ok': sum(c['matched'] for c in controls) <= 1, 'rows': controls},
        'G3': {'ok': bool(covered) and all(v['g3']['mask_pct'] >= 100 * TRACK_MIN for v in covered),
               'rows': [{k: v[k] for k in ('clip', 'leak_id', 'concept_id', 'g3')} for v in covered]},
        'G4a': {'ok': len(audio) > 0 and all(a['g4a_detected'] for a in audio), 'rows': audio},
        'G4b': {'ok': len(audio) > 0 and all(a['g4b_ok'] for a in audio),
                'rows': [{k: a[k] for k in ('clip', 'leak_id', 'label_span_s', 'bleep_intervals', 'coverage_pct', 'over_cover_s',
                                             'precision_method', 'pii_precision', 'bleep_pad_s')} for a in audio]},
        'G5': {'ok': not any(c['audit_unresolved'] for c in per_clip.values()), 'per_clip': per_clip,
               'note': 'reported, not a kill criterion'},
    }
    return {'verdict': verdict_of(g), 'criteria': g, 'notes': NOTES,
            'on_fail': 'GATE.md: if G1-G4 fail, stop Veil; fallback = Andaaz gate at Sunday breakfast'}


def render_md(r: dict) -> str:
    if r['verdict'] == 'NOT RUN':
        return f"# GATE: NOT RUN\n\n{r['reason']}\n"
    g = r['criteria']
    L = [f"# GATE RESULT: {r['verdict']}", '', '| criterion | result | evidence |', '| --- | --- | --- |']
    ok = lambda k: 'PASS' if g[k]['ok'] else ('FAIL' if k != 'G5' else 'UNRESOLVED listed')
    L.append(f"| G1 discovery | {ok('G1')} | {g['G1']['covered']}/{g['G1']['planted']} planted visual leaks matched by Spark concepts; "
             f"{g['G1']['covered_not_in_baseline']} with in_baseline=false |")
    L.append(f"| G2 false flags | {ok('G2')} | {g['G2']['controls_matched']}/{g['G2']['controls']} safe controls matched (limit 1) |")
    L.append(f"| G3 tracking | {ok('G3')} | " + '; '.join(f"{x['leak_id']} {x['g3']['mask_pct']}% (with held {x['g3']['with_held_pct']}%)"
                                                          for x in g['G3']['rows']) + ' |')
    L.append(f"| G4a detection | {ok('G4a')} | " + '; '.join(f"{a['leak_id']}: " + (f"{a['detected_digits']} exact={a['exact']} edit={a['edit_distance']}" if a['g4a_detected'] else 'no phone-like hit')
                                                          for a in g['G4a']['rows']) + ' |')
    L.append(f"| G4b localization | {ok('G4b')} | " + '; '.join(f"{a['leak_id']}: coverage {a['coverage_pct']}%, over-cover {a['over_cover_s']} s, "
                                                                f"method {a['precision_method']}/{','.join(a['pii_precision'])}, pad {a['bleep_pad_s']} s"
                                                          for a in g['G4b']['rows']) + ' |')
    L.append(f"| G5 output re-check | {ok('G5')} | " + ('no UNRESOLVED audit findings' if g['G5']['ok'] else '; '.join(
        f"{c}: {', '.join(v['audit_unresolved'])}" for c, v in g['G5']['per_clip'].items() if v['audit_unresolved'])) + ' |')
    L += ['', '## G1 per leak', '| clip | leak | concept | in_baseline | matched Spark concept | IoU | matched |', '| --- | --- | --- | --- | --- | --- | --- |']
    L += [f"| {v['clip']} | {v['leak_id']} | {v['concept']} | {v['in_baseline']} | {v['matched_prompt']} | {v['iou']} | {v['matched']} |" for v in g['G1']['rows']]
    L += ['', '## G2 per control', '| clip | control | best Spark concept | IoU | matched |', '| --- | --- | --- | --- | --- |']
    L += [f"| {c['clip']} | {c['control_id']} | {c['matched_prompt']} | {c['iou']} | {c['matched']} |" for c in g['G2']['rows']]
    L += ['', '## Interpretation notes'] + [f'- {n}' for n in r['notes']]
    if r['verdict'] == 'FAIL':
        L += ['', f"**{r['on_fail']}**"]
    return '\n'.join(L) + '\n'


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--labels', type=Path, default=Path('gate/labels'))
    p.add_argument('--runs', type=Path, default=Path('runs'))
    p.add_argument('--clips', type=Path, default=Path('gate/clips'))
    p.add_argument('--out', type=Path, default=Path('gate'))
    a = p.parse_args(argv)
    r = score(a.labels, a.runs, a.clips)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'gate_result.json').write_text(json.dumps(r, indent=1, default=str) + '\n')
    (a.out / 'GATE_RESULT.md').write_text(render_md(r))
    print(render_md(r))
    return {'PASS': 0, 'FAIL': 1, 'NOT RUN': 2}[r['verdict']]


if __name__ == '__main__':
    sys.exit(main())
