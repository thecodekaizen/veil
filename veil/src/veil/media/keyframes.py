"""Keyframes: ffmpeg scene changes UNION one frame per second, deduped within 0.3 s, capped."""
import re
import subprocess
from pathlib import Path

import cv2

from veil.schemas import Keyframe


def scene_times(video: Path, threshold: float = 0.3) -> list[float]:
    proc = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(video), '-vf', f"select='gt(scene,{threshold})',showinfo",
                           '-an', '-f', 'null', '-'], capture_output=True, text=True, check=True)
    return [float(t) for t in re.findall(r'pts_time:([0-9.]+)', proc.stderr)]


def select_times(duration_s: float, scene: list[float], interval_s: float = 1.0, dedupe_s: float = 0.3,
                 cap: int = 30) -> list[tuple[float, str]]:
    cands = [(t, 'scene') for t in scene if 0 <= t < duration_s]
    t = 0.0
    while t < duration_s:
        cands.append((round(t, 3), 'interval'))
        t += interval_s
    cands.sort()
    kept: list[tuple[float, str]] = []
    for t, reason in cands:
        if kept and t - kept[-1][0] < dedupe_s:
            if reason == 'scene' and kept[-1][1] == 'interval':
                kept[-1] = (t, reason)  # a scene change outranks a periodic frame
            continue
        kept.append((t, reason))
    if len(kept) > cap:
        scenes = [k for k in kept if k[1] == 'scene'][:cap]
        rest = [k for k in kept if k[1] == 'interval']
        slots = cap - len(scenes)
        if slots > 0 and rest:
            step = len(rest) / slots
            scenes += [rest[int(i * step)] for i in range(slots)]
        kept = sorted(scenes)
    return kept


def extract(video: Path, times: list[tuple[float, str]], outdir: Path, fps: float) -> list[Keyframe]:
    outdir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    frames = []
    try:
        for t, reason in times:
            idx = round(t * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            path = outdir / f'kf_{idx:05d}.jpg'
            cv2.imwrite(str(path), frame)
            frames.append(Keyframe(frame_idx=idx, t_s=round(idx / fps, 3), path=path.name, reason=reason))
    finally:
        cap.release()
    return frames
