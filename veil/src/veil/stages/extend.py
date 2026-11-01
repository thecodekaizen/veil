"""Extend: fix track-start coverage and apply temporal padding. Reads track.json (raw SAM) -> track_final.json.

Rules (frozen before gate footage):
- A track whose first mask frame is later than its concept's earliest discovery keyframe, or lies within
  START_NEAR_FRAMES of the clip start, is extended backward. First try SAM on the reversed segment starting at the
  first mask frame; if that yields no overlapping track, hold the first mask box back to the target frame.
  Target = the concept's earliest discovery keyframe, or frame 0 when the track starts within START_NEAR_FRAMES.
  (OCR is not used as an extra source of "earliest seen"; the independent OCR check is in the audit.)
- Every track gets +/- TEMPORAL_PAD frames: a frame within 3 of a mask frame that has no mask of its own holds that box.
"""
import subprocess
from pathlib import Path
from typing import Callable

from veil.schemas import DiscoverArtifact, Extension, MaskFrame, Masklet, TrackArtifact

START_NEAR_FRAMES = 15
TEMPORAL_PAD = 3
REVERSE_CONTEXT = 30  # frames after the first mask frame included in the reversed segment

# (concept_prompt, first_mask_frame, end_frame) -> {orig_frame: MaskFrame-compatible dict} from reversed SAM
ReverseSam = Callable[[str, int, int], dict[str, dict[int, dict]]]


def _iou(a, b) -> float:
    iw, ih = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    inter = max(0, iw) * max(0, ih)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _hold(src: MaskFrame, idx: int, origin: str) -> MaskFrame:
    return MaskFrame(frame_idx=idx, bbox=src.bbox, score=src.score, mask=None, origin=origin)


def extend_masklet(m: Masklet, target: int, prompt: str, reverse: ReverseSam | None, n_frames: int
                   ) -> tuple[Masklet, Extension]:
    first = min(m.frames, key=lambda f: f.frame_idx)
    f0 = first.frame_idx
    if f0 <= target:
        return m, Extension(concept_id=m.concept_id, track_id=m.track_id, method='none', from_frame=f0, to_frame=f0)
    have = {f.frame_idx for f in m.frames}
    method, note, added = 'held_back', '', []
    if reverse is not None:
        try:
            tracks = reverse(prompt, f0, min(n_frames - 1, f0 + REVERSE_CONTEXT))
            best, best_iou = None, 0.3
            for frames in tracks.values():
                if f0 in frames and frames[f0].get('box'):
                    i = _iou(frames[f0]['box'], first.bbox)
                    if i >= best_iou:
                        best, best_iou = frames, i
            if best:
                for idx in range(target, f0):
                    e = best.get(idx)
                    if e and e.get('frame'):
                        added.append(e['frame'].model_copy(update={'origin': 'sam_reversed'}))
                if {f.frame_idx for f in added} == set(range(target, f0)):
                    method = 'sam_reversed'
                else:  # incomplete reversed track: keep what SAM found, hold-fill the rest
                    note = f'reversed SAM covered {len(added)}/{f0 - target} frames; rest held'
                    got = {f.frame_idx for f in added}
                    added += [_hold(first, i, 'held_back') for i in range(target, f0) if i not in got]
            else:
                note = 'reversed SAM returned no track overlapping the first mask (IoU>=0.3); held'
        except Exception as exc:
            note = f'reversed SAM failed ({type(exc).__name__}: {str(exc)[:120]}); held'
    if not added:
        added = [_hold(first, i, 'held_back') for i in range(target, f0) if i not in have]
    frames = sorted(m.frames + added, key=lambda f: f.frame_idx)
    return (Masklet(concept_id=m.concept_id, track_id=m.track_id, frames=frames),
            Extension(concept_id=m.concept_id, track_id=m.track_id, method=method, from_frame=f0, to_frame=target, note=note))


def temporal_pad(m: Masklet, n_frames: int, pad: int = TEMPORAL_PAD) -> Masklet:
    by = {f.frame_idx: f for f in m.frames}
    for idx, f in sorted(by.items()):
        for d in range(1, pad + 1):
            for j in (idx - d, idx + d):
                if 0 <= j < n_frames and j not in by:
                    by[j] = _hold(f, j, 'temporal_pad')
    return Masklet(concept_id=m.concept_id, track_id=m.track_id, frames=[by[k] for k in sorted(by)])


def run(disc: DiscoverArtifact, track: TrackArtifact, n_frames: int, reverse: ReverseSam | None) -> TrackArtifact:
    prompts = {c.concept_id: (c.sam_prompt, c.first_frame_idx) for c in disc.concepts}
    out, exts = [], []
    for m in track.masklets:
        prompt, first_seen = prompts[m.concept_id]
        f0 = min(f.frame_idx for f in m.frames)
        target = 0 if f0 <= START_NEAR_FRAMES else first_seen
        m2, ext = extend_masklet(m, target, prompt, reverse, n_frames)
        out.append(temporal_pad(m2, n_frames))
        exts.append(ext)
    return track.model_copy(update={'masklets': out, 'extensions': exts,
        'notes': track.notes + f' Post-processed by extend: track-start coverage and +/-{TEMPORAL_PAD}-frame temporal padding.'})


def reversed_segment(video: Path, out: Path, end_frame: int) -> Path:
    """Frames 0..end_frame of video, reversed, silent, H.264 veryfast."""
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video), '-vf', f'trim=end_frame={end_frame + 1},reverse,setpts=PTS-STARTPTS',
                    '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', str(out)], check=True)
    return out


def make_reverse(c, ledger, root: Path, video: Path) -> ReverseSam:
    """Reversed-segment SAM: upload frames 0..end reversed, track the prompt, map reversed frame r -> original end - r."""
    import itertools
    import json
    from veil.providers.sam import segment_masks
    from veil.stages.track import to_masklets
    counter = itertools.count()

    def reverse(prompt: str, f0: int, end: int):
        k = next(counter)
        seg = reversed_segment(video, root / f'reverse-{k}-{end}.mp4', end)
        up = None
        try:
            with seg.open('rb') as stream:
                up = c.files.create(file=stream, purpose='user_data', expires_after={'anchor': 'created_at', 'seconds': 3600})
            raw = segment_masks(c, ledger, root, f'reverse-{k}-{end}', prompt, file_id=up.id, frame_count=end + 1)
        finally:
            if up:
                try:
                    c.files.delete(up.id)
                    deleted = True
                except Exception:
                    deleted = False
                (root / f'cloud-reverse-{k}.json').write_text(json.dumps(
                    {'file_id': up.id, 'scope': 'reversed run segment for SAM track-start extension', 'deleted': deleted}, indent=2) + '\n')
        out = {}
        for tid, frames in raw.items():
            remapped = {end - r: e for r, e in frames.items() if 0 <= end - r}
            ml = to_masklets('x', {tid: remapped})
            if ml:
                out[tid] = {f.frame_idx: {'box': list(f.bbox), 'frame': f} for f in ml[0].frames}
        return out
    return reverse
