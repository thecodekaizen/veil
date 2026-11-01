"""Audit: re-check the OUTPUT with checks that do not rely on the models that proposed the regions.

Every status is computed here from stored artifacts and decoded output pixels/audio:
COVERED = the listed checks found nothing left; UNRESOLVED = a check found something or a gap;
NOT_CHECKED = the check did not run. Nothing here proves the absence of identifying information.
"""
import re
import subprocess
import wave
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from rapidfuzz import fuzz

from veil.schemas import (AuditArtifact, Check, DiscoverArtifact, Finding, ListenArtifact, RedactArtifact,
                          TrackArtifact)
from veil.stages.redact import PAD_PX  # noqa: F401  (re-exported for callers)
from veil.validators.pii import phone_hits

OCR_FPS = 2
FACE_STEP = 5  # every 5th frame
BLACK_MAX = 25  # inside a covered box (edges trimmed for codec ringing), >= 99% of pixels must be <= this
EDGE_TRIM = 3
PHONE_RE = re.compile(r'(?<!\d)(?:\+?\d[\d ()-]{6,}\d)(?!\d)')
LIMITATIONS = [
    'Sampled-frame checks only (OCR at 2 fps, face detector every 5th frame); text or faces between samples are not examined.',
    'A frame where SAM returned no mask cannot be told apart from a frame where the object is absent; only gaps inside a track are flagged.',
    'The Haar-cascade face check is weak (misses profile/occluded faces; can fire on non-faces).',
    'Spoken-number re-check uses the same vendor family as the first pass, so it is not independent evidence.',
    'OCR runs on macOS only (Swift/Vision); elsewhere it is NOT_CHECKED.',
    'Speech timing has ~2 s window precision; Hinglish audio is untested.',
    'Non-phone identifiers (names, addresses) are not detected in speech or in OCR text unless they fall inside a covered region.',
]

OcrFn = Callable[[list[tuple[int, Path]], int, int], dict]   # frames -> inspect_text-style report with text_rows
FaceFn = Callable[[np.ndarray], list[tuple[int, int, int, int]]]
Relisten = Callable[[Path], ListenArtifact]


def haar_faces(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return [(int(x), int(y), int(x + w), int(y + h)) for x, y, w, h in
            cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))]


def _frames(video: Path, step: int):
    """Yield (frame_idx, ms, image) for every step-th decoded frame."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    n = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if n % step == 0:
            yield n, round(n / fps * 1000), img
        n += 1
    cap.release()


def _overlap(box_px, region) -> float:
    ax1, ay1, ax2, ay2 = box_px
    bx1, by1, bx2, by2 = region
    iw, ih = min(ax2, bx2) - max(ax1, bx1), min(ay2, by2) - max(ay1, by1)
    area = max(1, (ax2 - ax1) * (ay2 - ay1))
    return max(0, iw) * max(0, ih) / area


def _visual_findings(disc, track, red, out_video: Path) -> tuple[list[Finding], list[str]]:
    frames_by = {}
    for m in track.masklets:
        frames_by.setdefault(m.concept_id, set()).update(f.frame_idx for f in m.frames)
    boxes_by_frame: dict[str, dict[int, tuple]] = {}
    for r in red.regions:
        d = boxes_by_frame.setdefault(r.concept_id, {})
        for f in r.frames:
            d[f.frame_idx] = f.box
    cap = cv2.VideoCapture(str(out_video))
    out_frames = {}
    n = 0
    needed = {i for fs in frames_by.values() for i in fs}
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if n in needed:
            out_frames[n] = img
        n += 1
    cap.release()
    findings, empty = [], []
    for c in disc.concepts:
        fs = sorted(frames_by.get(c.concept_id, ()))
        skipped = next((s for s in track.skipped_concepts if s.concept_id == c.concept_id), None)
        if skipped:
            findings.append(Finding(finding_id=f'visual:{c.concept_id}', kind='visual', label=c.sam_prompt, source=c.source,
                                    status='NOT_CHECKED', reasons=[f'not tracked: {skipped.reason}']))
            continue
        if not fs:
            empty.append(c.sam_prompt)
            continue
        gaps = sorted(set(range(fs[0], fs[-1] + 1)) - set(fs))
        not_black = []
        for i in fs:
            x1, y1, x2, y2 = boxes_by_frame[c.concept_id][i]
            img = out_frames.get(i)
            inner = None if img is None else img[y1 + EDGE_TRIM:y2 - EDGE_TRIM, x1 + EDGE_TRIM:x2 - EDGE_TRIM]
            if inner is None or inner.size == 0 or float((inner > BLACK_MAX).mean()) > 0.01:
                not_black.append(i)
        reasons = []
        if gaps:
            reasons.append(f'{len(gaps)} frame(s) inside the track span have no mask (e.g. frame {gaps[0]})')
        if not_black:
            reasons.append(f'cover not found in decoded output on {len(not_black)} frame(s) (e.g. frame {not_black[0]})')
        findings.append(Finding(
            finding_id=f'visual:{c.concept_id}', kind='visual', label=c.sam_prompt, source=c.source,
            status='UNRESOLVED' if reasons else 'COVERED',
            reasons=reasons or [f'cover verified in decoded output on all {len(fs)} masked frames ({fs[0]}-{fs[-1]})'],
            evidence={'first_frame': fs[0], 'last_frame': fs[-1], 'masked_frames': len(fs), 'gap_frames': len(gaps)}))
    return findings, empty


def _ocr_findings(red, input_video, out_video, ocr: OcrFn, workdir: Path, fps: float, w: int, h: int):
    """Phone-like text visible in the output, and input text inside covered boxes that is still readable."""
    def sample(video, tag):
        d = workdir / tag
        d.mkdir(parents=True, exist_ok=True)
        stride = max(1, round(fps / OCR_FPS))
        items = []
        for n, ms, img in _frames(video, step=stride):
            p = d / f'f{n:05d}.png'
            cv2.imwrite(str(p), img)
            items.append((ms, p, n))
        return items
    covered_at: dict[int, list] = {}
    for r in red.regions:
        for f in r.frames:
            covered_at.setdefault(f.frame_idx, []).append(f.box)
    findings = []
    out_items = sample(out_video, 'ocr_out')
    out_rep = ocr([(ms, p) for ms, p, _ in out_items], w, h)
    if out_rep.get('status') != 'completed':
        return None, out_rep.get('reason', 'OCR did not complete')
    in_items = sample(input_video, 'ocr_in')
    in_rep = ocr([(ms, p) for ms, p, _ in in_items], w, h)
    if in_rep.get('status') != 'completed':
        return None, in_rep.get('reason', 'OCR did not complete')
    frame_of = {ms: n for ms, _, n in out_items}
    out_rows = out_rep.get('text_rows', [])
    for row in out_rows:
        if PHONE_RE.search(row['text']):
            findings.append(Finding(finding_id=f'ocr-phone:{row["time_ms"]}', kind='output_check',
                                    label='phone-like digits readable in output', source='ocr', status='UNRESOLVED',
                                    reasons=[f'OCR read a phone-like digit sequence at {row["time_ms"] / 1000:.1f}s'],
                                    evidence={'time_ms': row['time_ms']}))
    for row in in_rep.get('text_rows', []):
        norm = ''.join(ch for ch in row['text'] if ch.isalnum()).upper()
        if len(norm) < 4:
            continue
        x1, y1, x2, y2 = row['box'][0] * w, row['box'][1] * h, row['box'][2] * w, row['box'][3] * h
        n = frame_of.get(row['time_ms'])
        if n is None or not any(_overlap((x1, y1, x2, y2), b) >= 0.5 for b in covered_at.get(n, [])):
            continue
        same = [o for o in out_rows if o['time_ms'] == row['time_ms'] and
                fuzz.ratio(norm, ''.join(ch for ch in o['text'] if ch.isalnum()).upper()) >= 85]
        if same:
            findings.append(Finding(finding_id=f'ocr-residual:{row["time_ms"]}:{norm[:12]}', kind='output_check',
                                    label='text in a covered region still readable', source='ocr', status='UNRESOLVED',
                                    reasons=[f'OCR read text matching a covered input row at {row["time_ms"] / 1000:.1f}s'],
                                    evidence={'time_ms': row['time_ms']}))
    detail = (f'{len(out_items)} output frames and {len(in_items)} input frames at {OCR_FPS} fps; '
              f'{len(out_rows)} text rows read in output')
    return findings, detail


def _face_findings(red, input_video, out_video, face: FaceFn):
    def count(video):
        hits = {}
        for n, ms, img in _frames(video, step=FACE_STEP):
            b = face(img)
            if b:
                hits[n] = b
        return hits
    ins, outs = count(input_video), count(out_video)
    findings = [Finding(finding_id=f'face-output:{n}', kind='output_check', label='face-like region in output',
                        source='ocr', status='UNRESOLVED', reasons=[f'face detector fired on output frame {n}'],
                        evidence={'frame': n, 'boxes': [list(b) for b in boxes]})
                for n, boxes in sorted(outs.items())]
    return findings, f'face detector fired on {len(ins)} input and {len(outs)} output sampled frames'


def _mean_abs(wav: Path, a: float, b: float) -> float:
    with wave.open(str(wav)) as w:
        rate = w.getframerate()
        w.setpos(int(a * rate))
        pcm = np.frombuffer(w.readframes(int((b - a) * rate)), dtype=np.int16)
    return float(np.abs(pcm.astype(np.float32)).mean() / 32768) if len(pcm) else 0.0


def _audio_findings(listen: ListenArtifact, red: RedactArtifact, root: Path, relisten: Relisten | None):
    out_wav = root / 'output-audio.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(root / red.output_path), '-vn', '-ac', '1', '-ar', '24000',
                    '-c:a', 'pcm_s16le', str(out_wav)], check=True)
    redo = relisten(out_wav) if relisten else None
    findings = []
    for i, p in enumerate(listen.pii):
        covered = any(a <= p.t_start and b >= p.t_end for a, b in red.muted_intervals)
        level = max((_mean_abs(out_wav, max(0, a), b) for a, b in red.muted_intervals), default=1.0)
        reasons = []
        if not covered:
            reasons.append('muted intervals do not cover the whole detected span')
        if level > 0.002:
            reasons.append(f'output audio is not silent inside the muted interval (mean |x| {level:.4f})')
        if redo is None:
            status, reasons = 'NOT_CHECKED', reasons + ['spoken-number re-check did not run']
        elif redo.pii:
            reasons.append(f're-transcription of the output still shows a phone-like run ({len(redo.pii)})')
        if redo is not None:
            status = 'UNRESOLVED' if reasons else 'COVERED'
            if not reasons:
                reasons = ['detected span is inside a muted interval, output is silent there, and re-transcription '
                           'of the output found no phone-like digit run']
        findings.append(Finding(finding_id=f'audio:{i}', kind='audio', label='spoken phone-like number', source='voice',
                                status=status, reasons=reasons,
                                evidence={'t_start': p.t_start, 't_end': p.t_end, 'precision': p.precision,
                                          'muted_intervals': [list(m) for m in red.muted_intervals]}))
    return findings, redo is not None


def run(root: Path, ocr: OcrFn | None, face: FaceFn | None, relisten: Relisten | None) -> AuditArtifact:
    disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
    track = TrackArtifact.model_validate_json((root / 'track.json').read_text())
    listen = ListenArtifact.model_validate_json((root / 'listen.json').read_text())
    red = RedactArtifact.model_validate_json((root / 'redact.json').read_text())
    cap = cv2.VideoCapture(str(root / 'input.mp4'))
    fps, w, h = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    out = root / red.output_path
    findings, empty = _visual_findings(disc, track, red, out)
    checks = [Check(check_id='cover_pixels', description='Covered boxes are black in the decoded output', status='RAN'),
              Check(check_id='track_gaps', description='No mask gaps inside each concept track span', status='RAN')]
    if ocr:
        res, detail = _ocr_findings(red, root / 'input.mp4', out, ocr, root / 'audit_frames', fps, w, h)
        if res is None:
            checks.append(Check(check_id='ocr_output', description='Independent OCR on output frames',
                                status='NOT_CHECKED', detail=detail))
        else:
            findings += res
            checks.append(Check(check_id='ocr_output', description='Independent OCR on output frames (phone-like text; '
                                'covered input text still readable)', status='RAN', detail=detail))
    else:
        checks.append(Check(check_id='ocr_output', description='Independent OCR on output frames', status='NOT_CHECKED',
                            detail='no OCR adapter supplied'))
    if face:
        res, detail = _face_findings(red, root / 'input.mp4', out, face)
        findings += res
        checks.append(Check(check_id='face_output', description='Haar-cascade face detector on output frames', status='RAN',
                            detail=detail))
    else:
        checks.append(Check(check_id='face_output', description='Face detector on output frames', status='NOT_CHECKED'))
    audio, rechecked = _audio_findings(listen, red, root, relisten)
    findings += audio
    checks.append(Check(check_id='audio_silence', description='Output audio is silent inside muted intervals', status='RAN'))
    checks.append(Check(check_id='audio_recheck', description='Re-transcription of output audio for phone-like digit runs',
                        status='RAN' if rechecked else 'NOT_CHECKED'))
    art = AuditArtifact(findings=findings, checks=checks, concepts_without_masks=empty, limitations=LIMITATIONS)
    (root / 'audit.json').write_text(art.model_dump_json(indent=1) + '\n')
    return art
