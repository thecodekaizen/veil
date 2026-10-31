"""debug-overlay: masks + concept label + source burned onto the run input (H.264, -preset veryfast)."""
import base64
import subprocess
from pathlib import Path

import cv2
import numpy as np

from veil.schemas import DiscoverArtifact, TrackArtifact

AMBER, GREY = (74, 176, 232), (150, 150, 150)  # BGR


def decode_mask(mask) -> np.ndarray:
    bits = np.unpackbits(np.frombuffer(base64.b64decode(mask.packed_b64), dtype=np.uint8))
    return bits[:mask.width * mask.height].reshape(mask.height, mask.width)


def render(root: Path) -> Path:
    disc = DiscoverArtifact.model_validate_json((root / 'discover.json').read_text())
    track = TrackArtifact.model_validate_json((root / 'track.json').read_text())
    source = {c.concept_id: (c.source, c.sam_prompt) for c in disc.concepts}
    per_frame: dict[int, list] = {}
    for m in track.masklets:
        for f in m.frames:
            per_frame.setdefault(f.frame_idx, []).append((m, f))
    cap = cv2.VideoCapture(str(root / 'input.mp4'))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    raw = root / 'overlay.raw.mp4'
    out = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        over = frame.copy()
        labels = []
        for m, f in per_frame.get(idx, []):
            src, prompt = source.get(m.concept_id, ('?', m.concept_id))
            color = AMBER if src == 'spark' else GREY
            l, t, r, b = (int(v) for v in f.bbox)
            if f.mask:
                ml, mt, mr, mb = (int(round(v)) for v in f.mask.bounds)
                mk = decode_mask(f.mask).astype(np.uint8)
                if mr > ml and mb > mt:
                    mk = cv2.resize(mk, (mr - ml, mb - mt), interpolation=cv2.INTER_NEAREST)
                    y0, x0 = max(mt, 0), max(ml, 0)
                    sub = mk[y0 - mt:min(mb, h) - mt, x0 - ml:min(mr, w) - ml]
                    region = over[y0:y0 + sub.shape[0], x0:x0 + sub.shape[1]]
                    region[sub > 0] = color
            cv2.rectangle(frame, (l, t), (r, b), color, 1)
            labels.append((l, max(t - 4, 12), f'{src}: {prompt}'))
        frame = cv2.addWeighted(over, 0.5, frame, 0.5, 0)
        used = []
        for x, y, text in labels:
            while any(abs(x - ux) < 120 and abs(y - uy) < 14 for ux, uy in used):
                y += 14
            used.append((x, y))
            cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f'frame {idx}', (6, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        out.write(frame)
        idx += 1
    cap.release()
    out.release()
    target = root / 'overlay.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw), '-c:v', 'libx264', '-preset', 'veryfast',
                    '-crf', '20', '-pix_fmt', 'yuv420p', str(target)], check=True)
    raw.unlink()
    return target
