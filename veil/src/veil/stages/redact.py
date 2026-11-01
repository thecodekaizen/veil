"""Redact: opaque-cover every tracked mask box and mute the listen-stage bleep intervals.

Models proposed the regions; this stage only applies them and records exactly what it applied (redact.json).
"""
import hashlib
import subprocess
from pathlib import Path

import cv2

from veil.media.redact import apply_redactions
from veil.schemas import (AppliedRegion, DiscoverArtifact, ListenArtifact, RedactArtifact, RegionFrame,
                          TrackArtifact)

PAD_PX = 12


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan(disc: DiscoverArtifact, track: TrackArtifact, w: int, h: int, pad: int = PAD_PX) -> list[AppliedRegion]:
    src = {c.concept_id: c for c in disc.concepts}
    out = []
    for m in track.masklets:
        frames = []
        for f in m.frames:
            x1, y1, x2, y2 = f.bbox
            frames.append(RegionFrame(frame_idx=f.frame_idx, box=(max(0, int(x1) - pad), max(0, int(y1) - pad),
                                                                  min(w, int(x2) + pad + 1), min(h, int(y2) + pad + 1))))
        c = src[m.concept_id]
        out.append(AppliedRegion(concept_id=m.concept_id, track_id=m.track_id, source=c.source,
                                 sam_prompt=c.sam_prompt, frames=frames))
    return out


def run(root: Path, pad: int = PAD_PX) -> RedactArtifact:
    disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
    track = TrackArtifact.model_validate_json((root / 'track.json').read_text())
    listen = ListenArtifact.model_validate_json((root / 'listen.json').read_text())
    video = root / 'input.mp4'
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    regions = plan(disc, track, w, h, pad)
    by_frame: dict[int, list] = {}
    for r in regions:
        for f in r.frames:
            by_frame.setdefault(f.frame_idx, []).append(f.box)
    silent = root / 'output-silent.mp4'
    writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        # boxes are already padded; apply_redactions pads again, so pass padding=0
        apply_redactions(frame, [(b, 'cover') for b in by_frame.get(n, [])], padding=0)
        writer.write(frame)
        n += 1
    writer.release(); cap.release()
    out = root / 'output.mp4'
    args = ['ffmpeg', '-v', 'error', '-y', '-i', str(silent), '-i', str(video), '-map', '0:v:0', '-map', '1:a:0?',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
            '-movflags', '+faststart', '-map_metadata', '-1']
    if listen.bleep_intervals:
        args += ['-af', ','.join(f"volume=0:enable='between(t,{a:.3f},{b:.3f})'" for a, b in listen.bleep_intervals)]
    subprocess.run(args + [str(out)], check=True)
    silent.unlink()
    art = RedactArtifact(input_sha256=_sha(video), output_path='output.mp4', output_sha256=_sha(out), pad_px=pad,
                         action='cover', regions=regions, muted_intervals=list(listen.bleep_intervals))
    (root / 'redact.json').write_text(art.model_dump_json(indent=1) + '\n')
    return art
