"""Run S2 stages (keyframes, discover, track, listen) writing validated artifacts to runs/<id>/."""
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

import cv2

from veil.ledger import LockedCalls
from veil.media import keyframes as kf_mod
from veil.providers.common import Calls, client
from veil.providers.sam import segment_masks
from veil.schemas import DiscoverArtifact, KeyframeArtifact, ListenArtifact, TrackArtifact
from veil.stages import discover as discover_stage
from veil.stages import listen as listen_stage
from veil.stages import track as track_stage

STAGES = ['keyframes', 'discover', 'track', 'extend', 'listen', 'redact', 'audit', 'report']
BLEEP_PAD_S = 0.5  # chosen on the synthetic clip only; rationale in docs/decisions.md


def find_env() -> Path:
    for d in [Path.cwd(), *Path.cwd().parents]:
        if (d / '.env').exists():
            return d / '.env'
    raise FileNotFoundError('.env with MODEL_API_KEY not found')


def _write(root: Path, name: str, model) -> None:
    (root / f'{name}.json').write_text(model.model_dump_json(indent=1) + '\n')


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(clip: Path, run_id: str, stages: list[str], runs_dir: Path = Path('runs'),
        bleep_pad_s: float = BLEEP_PAD_S) -> Path:
    root = runs_dir / run_id
    root.mkdir(parents=True, exist_ok=True)
    video = root / 'input.mp4'
    if not video.exists():
        shutil.copyfile(clip, video)
    cap = cv2.VideoCapture(str(video))
    fps, w, h = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    duration = n_frames / fps
    env = find_env()
    c = client(env)
    ledger = LockedCalls(Calls(root, max_calls=200))

    if 'keyframes' in stages:
        times = kf_mod.select_times(duration, kf_mod.scene_times(video))
        frames = kf_mod.extract(video, times, root / 'keyframes', fps)
        _write(root, 'keyframes', KeyframeArtifact(input_sha256=_sha256(video), fps=fps, width=w, height=h,
                                                   duration_s=duration, keyframes=frames))
    if 'discover' in stages:
        kfa = KeyframeArtifact.model_validate_json((root / 'keyframes.json').read_text())
        ask = discover_stage.make_spark_ask(c, ledger, root)
        _write(root, 'discover', discover_stage.run(kfa.keyframes, root / 'keyframes', ask))
    if 'track' in stages:
        disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
        uploaded = None
        try:
            with video.open('rb') as stream:
                uploaded = c.files.create(file=stream, purpose='user_data',
                                          expires_after={'anchor': 'created_at', 'seconds': 3600})
            _write_json(root / 'cloud-upload.json', {'file_id': uploaded.id, 'scope': 'run input video for SAM tracking'})

            def call_sam(name, prompt):
                return segment_masks(c, ledger, root, name, prompt, file_id=uploaded.id, frame_count=n_frames)

            _write(root, 'track', track_stage.run(disc, call_sam, n_frames))
        finally:
            if uploaded:
                try:
                    c.files.delete(uploaded.id)
                    _write_json(root / 'cloud-cleanup.json', {'deleted': True})
                except Exception:
                    _write_json(root / 'cloud-cleanup.json', {'deleted': False, 'needs_attention': True})
    if 'extend' in stages:
        from veil.stages import extend as extend_stage
        disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
        raw_track = TrackArtifact.model_validate_json((root / 'track.json').read_text())
        _write(root, 'track_final', extend_stage.run(disc, raw_track, n_frames,
                                                     extend_stage.make_reverse(c, ledger, root, video)))
    if 'listen' in stages:
        wav = root / 'audio.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video), '-vn', '-ac', '1', '-ar', '24000',
                        '-c:a', 'pcm_s16le', str(wav)], check=True)
        _write(root, 'listen', listen_stage.run(wav, listen_stage.make_transcribe(c.api_key, ledger), bleep_pad_s))
    if 'redact' in stages:
        from veil.stages import redact as redact_stage
        redact_stage.run(root)
    if 'audit' in stages:
        from veil.stages import audit as audit_stage
        from veil.verification.ocr import inspect_text
        cache = root / 'audit_cache'
        transcribe = listen_stage.make_transcribe(c.api_key, ledger, name_prefix=f'audit-listen-{int(time.time())}')
        audit_stage.run(root,
                        lambda frames, fw, fh: inspect_text(frames, fw, fh, cache, include_text_rows=True),
                        audit_stage.haar_faces,
                        lambda wav: listen_stage.run(wav, transcribe, bleep_pad_s))
    if 'report' in stages:
        from veil import report
        report.render(root)
    return root


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + '\n')


def summarize(root: Path) -> str:
    lines = []
    if (root / 'discover.json').exists():
        disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
        track = TrackArtifact.model_validate_json((root / 'track.json').read_text()) if (root / 'track.json').exists() else None
        frames_by = {}
        if track:
            for m in track.masklets:
                frames_by.setdefault(m.concept_id, set()).update(f.frame_idx for f in m.frames if f.mask)
        skipped = {s.concept_id: s.reason for s in track.skipped_concepts} if track else {}
        lines.append(f'{"source":9} {"sam_prompt":28} {"conf":>5} {"frames w/ mask":>14}  status')
        for c in disc.concepts:
            n = len(frames_by.get(c.concept_id, ()))
            lines.append(f'{c.source:9} {c.sam_prompt[:28]:28} {c.max_confidence:5.2f} {n:14d}  '
                         f'{"NOT_CHECKED: " + skipped[c.concept_id] if c.concept_id in skipped else ""}')
        if disc.errors:
            lines.append(f'discover errors: {len(disc.errors)}')
    if (root / 'listen.json').exists():
        lis = ListenArtifact.model_validate_json((root / 'listen.json').read_text())
        lines.append(f'transcript: {lis.transcript_text!r}')
        for p in lis.pii:
            lines.append(f'spoken PII: digits={p.normalized_value} {p.t_start:.2f}-{p.t_end:.2f}s '
                         f'precision={p.precision} mobile_pattern={p.mobile_pattern}')
        lines.append(f'bleep intervals (pad {lis.bleep_pad_s}s): {[(round(a, 2), round(b, 2)) for a, b in lis.bleep_intervals]}')
    return '\n'.join(lines)


def summarize_audit(root: Path) -> str:
    from veil.schemas import AuditArtifact
    if not (root / 'audit.json').exists():
        return ''
    a = AuditArtifact.model_validate_json((root / 'audit.json').read_text())
    lines = ['', 'audit:']
    lines += [f'  {f.status:11} {f.kind:12} {f.label[:34]:34} {f.reasons[0][:90]}' for f in a.findings]
    lines += [f'  check {c.status:11} {c.check_id}: {c.detail[:80]}' for c in a.checks]
    return '\n'.join(lines)
