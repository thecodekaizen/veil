"""Contact sheets + label templates for gate clips.

uv run --project veil python -m gate.prepare_labels [--clips gate/clips] [--out gate/frames] [--labels gate/labels]

For each CLIP.mp4: gate/frames/CLIP/sheet_NN.png (2 fps tiles, timestamp + 10% grid with source-pixel
values on every tile) and gate/labels/CLIP.json, a template pre-filled with sha256/fps. Existing label
files are never overwritten (labels are frozen once committed).
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from veil.label import probe, sha256_file

SHEET_FPS = 2
COLS, ROWS, TILE_W = 4, 5, 480


def tile(frame, t_s, src_w, src_h):
    h, w = frame.shape[:2]
    scale = TILE_W / w
    img = cv2.resize(frame, (TILE_W, int(h * scale)))
    th = img.shape[0]
    for i in range(1, 10):
        x, y = int(TILE_W * i / 10), int(th * i / 10)
        cv2.line(img, (x, 0), (x, th), (0, 255, 255), 1)
        cv2.line(img, (0, y), (TILE_W, y), (0, 255, 255), 1)
        cv2.putText(img, str(int(src_w * i / 10)), (x + 2, 11), cv2.FONT_HERSHEY_PLAIN, 0.8, (0, 255, 0), 1)
        cv2.putText(img, str(int(src_h * i / 10)), (2, y - 2), cv2.FONT_HERSHEY_PLAIN, 0.8, (255, 128, 0), 1)
    cv2.rectangle(img, (0, th - 18), (110, th), (0, 0, 0), -1)
    cv2.putText(img, f't={t_s:5.1f}s', (4, th - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return img


def sheets(clip: Path, out: Path, meta: dict) -> list[Path]:
    folder = out / clip.stem
    folder.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(clip))
    tiles, t = [], 0.0
    while t <= meta['duration']:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            break
        tiles.append(tile(frame, t, meta['width'], meta['height']))
        t += 1 / SHEET_FPS
    cap.release()
    paths = []
    per = COLS * ROWS
    for page, start in enumerate(range(0, len(tiles), per), 1):
        chunk = tiles[start:start + per]
        th = chunk[0].shape[0]
        canvas = np.zeros((ROWS * th, COLS * TILE_W, 3), dtype=np.uint8)
        for k, img in enumerate(chunk):
            r, c = divmod(k, COLS)
            canvas[r * th:(r + 1) * th, c * TILE_W:(c + 1) * TILE_W] = img
        path = folder / f'sheet_{page:02d}.png'
        cv2.imwrite(str(path), canvas)
        paths.append(path)
    return paths


def template(clip: Path, meta: dict) -> dict:
    box = {'t_s': None, 'x': None, 'y': None, 'w': None, 'h': None}
    return {
        'clip_id': clip.stem, 'clip_sha256': sha256_file(clip), 'fps': round(meta['fps'], 3),
        'leaks': [{'leak_id': f'L{i}', 'kind': 'visual', 'concept': '', 'in_baseline': None,
                   'visible_ranges': [], 'ref_boxes': [dict(box), dict(box)], 'audio': None} for i in range(1, 5)]
                 + [{'leak_id': 'A1', 'kind': 'audio', 'concept': 'spoken fictional phone number',
                     'in_baseline': False, 'visible_ranges': [], 'ref_boxes': [],
                     'audio': {'text': '', 'digits': '', 't_start': None, 't_end': None}}],
        'safe_controls': [{'control_id': f'C{i}', 'description': '', 'visible_ranges': [],
                           'ref_boxes': [dict(box)]} for i in range(1, 4)],
        '_instructions': 'Fill every field; delete unused leaks/controls and this key. Boxes are source pixels '
                         '(x,y = top-left). Aim for 2-3 ref_boxes per visual leak. Validate with '
                         'python -m gate.validate_labels FILE.',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clips', type=Path, default=Path('gate/clips'))
    ap.add_argument('--out', type=Path, default=Path('gate/frames'))
    ap.add_argument('--labels', type=Path, default=Path('gate/labels'))
    args = ap.parse_args()
    clips = sorted(args.clips.glob('*.mp4')) + sorted(args.clips.glob('*.mov'))
    if not clips:
        raise SystemExit(f'no clips in {args.clips}')
    args.labels.mkdir(parents=True, exist_ok=True)
    for clip in clips:
        meta = probe(clip)
        pages = sheets(clip, args.out, meta)
        target = args.labels / f'{clip.stem}.json'
        if target.exists():
            note = 'label file exists; NOT overwritten'
        else:
            target.write_text(json.dumps(template(clip, meta), indent=2) + '\n')
            note = f'template written: {target}'
        print(f'{clip.name}: {meta["width"]}x{meta["height"]} {meta["fps"]:.2f} fps {meta["duration"]:.1f}s, '
              f'{len(pages)} sheet(s) in {args.out / clip.stem}; {note}')


if __name__ == '__main__':
    main()
