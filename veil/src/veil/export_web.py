"""export-web: copy a run's input/output video and a compact manifest.json for the static demo UI.

The manifest carries only what the UI shows (applied region boxes, audit findings, checks, transcript, timing).
Masks and raw model responses are not exported.
"""
import json
import shutil
from pathlib import Path

from veil.report import FOOTER, load_calls
from veil.schemas import AuditArtifact, DiscoverArtifact, ListenArtifact, RedactArtifact

import cv2


def export(root: Path, out: Path, provenance: str) -> Path:
    red = RedactArtifact.model_validate_json((root / 'redact.json').read_text())
    audit = AuditArtifact.model_validate_json((root / 'audit.json').read_text())
    listen = ListenArtifact.model_validate_json((root / 'listen.json').read_text())
    disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
    calls = load_calls(root)
    verify = json.loads((root / 'verify.json').read_text()) if (root / 'verify.json').exists() else None
    cap = cv2.VideoCapture(str(root / 'input.mp4'))
    fps, n = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / 'input.mp4', out / 'input.mp4')
    shutil.copyfile(root / red.output_path, out / 'output.mp4')
    natural = json.loads((root / 'natural.json').read_text()) if (root / 'natural.json').exists() else None
    if natural:
        shutil.copyfile(root / natural['output'], out / 'output_natural.mp4')
    why = {c.concept_id: c.why_identifying for c in disc.concepts}
    regions = [{'concept_id': r.concept_id, 'label': r.sam_prompt, 'source': r.source, 'why': why.get(r.concept_id, ''),
                'frames': [[f.frame_idx, *f.box] for f in r.frames]} for r in red.regions]
    manifest = {
        'run_id': root.name, 'provenance': provenance, 'footer': FOOTER,
        'video': {'fps': fps, 'frames': n, 'width': w, 'height': h, 'duration_s': n / fps},
        'regions': regions,
        'findings': [f.model_dump() for f in audit.findings], 'checks': [c.model_dump() for c in audit.checks],
        'concepts_without_masks': audit.concepts_without_masks, 'limitations': audit.limitations,
        'audio': {'transcript': listen.transcript_text, 'method': listen.method, 'window_s': listen.window_s,
                  'bleep_pad_s': listen.bleep_pad_s, 'muted_intervals': [list(m) for m in red.muted_intervals],
                  'pii': [{'digits': p.normalized_value, 't_start': p.t_start, 't_end': p.t_end, 'precision': p.precision}
                          for p in listen.pii]},
        'cost': {'calls': len(calls), 'failed': sum(c.get('status') != 'completed' for c in calls),
                 'estimated_usd': round(sum(c.get('estimated_usd') or 0 for c in calls), 2),
                 'unpriced': sum(c.get('estimated_usd') is None for c in calls)},
        'verify': None if verify is None else [
            {k: r.get(k) for k in ('track_id', 'concept_id', 'status', 'claimed', 'matched', 'ocr_text', 'frames_checked')}
            for r in verify['results'] if r['status'] != 'not_applicable'],
        'models': {'discover': disc.model_id, 'track': 'sam-3.1', 'listen': listen.model_id},
        'natural': None if not natural else {k: natural[k] for k in ('replacements', 'text_surface_frames', 'fallback_cover_frames', 'cover_regions')}
                   | {'audit': {k: natural['audit'][k] for k in ('status', 'sampled_frames', 'check')}, 'residual_words': len(natural['audit']['residual_original_words'])},
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, separators=(',', ':')) + '\n')
    return out / 'manifest.json'
