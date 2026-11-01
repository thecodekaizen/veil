"""Verify (POST-GATE, not part of the frozen gate configuration): does a SAM mask contain the text its concept claims?

Spark describes a candidate with specific text (e.g. "KULKARNI - 12"); SAM may ground the prompt on a different object.
For each Spark masklet whose concepts quote text (ALL-CAPS words of >= 4 letters, or quoted strings), local OCR reads
the masked box on up to 3 frames. If no claimed token is found (fuzzy, ratio >= 0.8) the masklet is REJECTED and listed
in verify.json; it is removed from track_final.json (the original is kept as track_final.unverified.json).
Concepts that quote no text are left unchanged ("not_applicable"): this check cannot vouch for them.
OCR is local (macOS Vision) and can misread; a rejected-by-OCR true leak is a risk this stage records, not hides."""
import re
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

import cv2

from veil.schemas import DiscoverArtifact, TrackArtifact

RATIO_MIN = 0.8
SAMPLES = 3
PAD_PX = 8

# crops [(time_ms, path)], width, height -> [{'text': str, ...}] rows
OcrRows = Callable[[list, int, int], list[dict]]


def claimed_tokens(text: str) -> list[str]:
    quoted = [t.strip(" '\"").upper() for t in re.findall(r"""['"]([^'"]{3,})['"]""", text)]
    caps = re.findall(r'\b[A-Z][A-Z]{3,}\b', text)
    return sorted({t for t in quoted + caps if len(t) >= 4})


def found(token: str, rows: list[str]) -> bool:
    token = token.upper()
    for row in rows:
        row = row.upper()
        if token in row:
            return True
        for w in re.findall(r'\w+', row):
            if SequenceMatcher(None, token, w).ratio() >= RATIO_MIN:
                return True
    return False


def run(root: Path, ocr_rows: OcrRows) -> dict:
    disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
    final = root / 'track_final.json'
    backup = root / 'track_final.unverified.json'
    if not backup.exists():
        backup.write_text(final.read_text())
    track = TrackArtifact.model_validate_json(backup.read_text())
    cand = {c.candidate_id: c for c in disc.candidates}
    concept_claims = {}
    for c in disc.concepts:
        text = ' '.join(f"{cand[i].concept} {cand[i].sam_prompt}" for i in c.candidate_ids if i in cand)
        concept_claims[c.concept_id] = (c.source, claimed_tokens(text))
    cap = cv2.VideoCapture(str(root / 'input.mp4'))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    kept, results = [], []
    for m in track.masklets:
        source, tokens = concept_claims.get(m.concept_id, ('baseline', []))
        if source != 'spark' or not tokens:
            kept.append(m)
            results.append({'track_id': m.track_id, 'concept_id': m.concept_id, 'status': 'not_applicable', 'claimed': tokens})
            continue
        sam = [f for f in m.frames if f.origin == 'sam'] or m.frames
        picks = sorted({sam[0].frame_idx, sam[len(sam) // 2].frame_idx, sam[-1].frame_idx})[:SAMPLES]
        by_idx = {f.frame_idx: f for f in sam}
        crops, tmp = [], Path(tempfile.mkdtemp())
        for i in picks:
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, img = cap.read()
            if not ok:
                continue
            x0, y0, x1, y1 = [int(v) for v in by_idx[i].bbox]
            crop = img[max(0, y0 - PAD_PX):min(h, y1 + PAD_PX), max(0, x0 - PAD_PX):min(w, x1 + PAD_PX)]
            if crop.size == 0:
                continue
            p = tmp / f'{m.track_id.replace(":", "_")}_{i}.jpg'
            cv2.imwrite(str(p), crop)
            crops.append((int(i / fps * 1000), p, crop.shape[1], crop.shape[0]))
        texts = []
        for t, p, cw, ch in crops:
            texts.extend(r['text'] for r in ocr_rows([(t, p)], cw, ch))
        hit = [t for t in tokens if found(t, texts)]
        status = 'verified' if hit else 'rejected'
        if hit:
            kept.append(m)
        results.append({'track_id': m.track_id, 'concept_id': m.concept_id, 'status': status, 'claimed': tokens,
                        'matched': hit, 'ocr_text': texts[:12], 'frames_checked': picks})
    cap.release()
    out = track.model_copy(update={'masklets': kept})
    final.write_text(out.model_dump_json(indent=1))
    report = {'stage': 'verify', 'post_gate': True, 'results': results,
              'rejected': [r['track_id'] for r in results if r['status'] == 'rejected']}
    import json
    (root / 'verify.json').write_text(json.dumps(report, indent=1))
    return report


def macos_ocr_rows(cache: Path) -> OcrRows:
    from veil.verification.ocr import inspect_text

    def rows(frames, w, h):
        rep = inspect_text(frames, w, h, cache, include_text_rows=True)
        return rep.get('text_rows', [])
    return rows
