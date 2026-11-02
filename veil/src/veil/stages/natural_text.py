"""Natural export (opt-in): replace identifying TEXT surfaces with fictional text instead of black boxes.

Reads the run's artifacts (input.mp4, redact.json regions, verify.json OCR rows) and writes output_natural.mp4 + natural.json.
- A region whose mask was VERIFIED by the mask check carries the text OCR read inside it (e.g. "KULKARNI - 12"). Those are
  text surfaces: each frame re-renders the surface with the original's sampled background and ink colours, the same line
  layout, and identifying words swapped for fictional ones from a fixed allowlist (names, digits).
- Every other region (faces, plates, masks with no verified text, e.g. a mask on a code panel) keeps an opaque cover.
- The natural file is then AUDITED on its own: local OCR on output frames must not read any original identifying word.
  Frames with a residual fall back to an opaque cover for that surface, and the receipt counts them.
Audio is taken from the already-muted output.mp4. Nothing here calls a model.
"""
import json
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from veil.stages.verify import claimed_tokens

FONT_PATHS = ['/System/Library/Fonts/Helvetica.ttc', '/System/Library/Fonts/SFNS.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
FICTIONAL_SURNAMES = ['SHARMA', 'MEHTA', 'IYER', 'NAIR']
FICTIONAL_GIVEN = ['Aarav', 'Ishaan', 'Kabir', 'Vihaan']
MERGE_IOU = 0.5
# Words Spark uses to DESCRIBE a surface (or that are ordinary UI text), never identifiers to replace.
GENERIC = {'TEXT', 'NAME', 'NAMES', 'LABEL', 'GOLD', 'BLACK', 'WHITE', 'MESSAGE', 'MESSAGES', 'PHONE', 'NOTIFICATION', 'BANNER', 'OVERLAY',
           'CAPTION', 'PLATE', 'NUMBER', 'SCREEN', 'SIGN', 'BOARD', 'CARD', 'BADGE', 'LOGO', 'SURNAME', 'FIRST', 'FULL', 'CONTACT',
           'SENDER', 'PERSONAL', 'DOOR', 'HOUSE', 'FLAT', 'APARTMENT', 'NAMEPLATE', 'PARCEL', 'DELIVERY', 'GATE', 'YOUR', 'FROM',
           'WITH', 'THIS', 'THAT', 'HERE', 'THERE', 'NOW', 'TODAY', 'NEW', 'CALL', 'CHAT', 'APP', 'ALERT'}
RATIO = 0.8

OcrRows = Callable[[list, int, int], list[dict]]  # [(time_ms, path)], w, h -> rows with 'text', 'time_ms'


def _font(size: int, bold: bool = False):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size, index=1 if bold and p.endswith('.ttc') else 0)
        except OSError:
            continue
    return ImageFont.load_default()


def _iou(a, b) -> float:
    iw, ih = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    inter = max(0, iw) * max(0, ih)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def parse_overrides(pairs: list[str]) -> dict[str, str]:
    """['Rohan=Priya', 'Kulkarni=Verma'] -> {'ROHAN': 'Priya', 'KULKARNI': 'Verma'} (user-chosen replacements)."""
    out = {}
    for p in pairs:
        old, sep, new = p.partition('=')
        if not sep or not old.strip() or not new.strip():
            raise ValueError(f'replacement must look like OLD=NEW, got {p!r}')
        out[old.strip().upper()] = new.strip()
    return out


def identifying_words(claims: list[str]) -> list[str]:
    """Words of Spark's claimed text that identify someone: names and codes, not sentences or descriptions.
    A quoted claim of 3+ words is a sentence ("YOUR PARCEL IS AT THE GATE"), so its words are skipped; generic words are skipped."""
    out = []
    for c in claims:
        ws = re.findall(r'[A-Za-z]{4,}', c)
        if len(re.findall(r'[A-Za-z]+', c)) >= 3:
            continue
        out += [w for w in ws if w.upper() not in GENERIC]
    return out


def build_mapping(words: list[str], claims: list[str], overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Identifying word -> fictional word. The first word of a two-word claimed name ("Rohan" in "Rohan Kulkarni")
    maps to a fictional given name; every other identifying word maps to a fictional surname. Deterministic.
    `overrides` (UPPERCASE word -> replacement) win over the built-in pools for the words they name."""
    given = set()
    for c in claims:
        ws = re.findall(r'[A-Za-z]+', c)
        if len(ws) >= 2 and all(len(x) >= 3 for x in ws[:2]):
            given.add(ws[0].upper())
    mapping, g, s = {}, 0, 0
    for w in words:
        key = w.upper()
        if key in mapping:
            continue
        if key in given:
            mapping[key] = FICTIONAL_GIVEN[g % len(FICTIONAL_GIVEN)]; g += 1
        else:
            mapping[key] = FICTIONAL_SURNAMES[s % len(FICTIONAL_SURNAMES)]; s += 1
    for key, rep in (overrides or {}).items():
        if key.upper() in mapping:
            mapping[key.upper()] = rep
    return mapping


def rewrite(line: str, mapping: dict[str, str]) -> str:
    """Swap identifying words (case-aware) and every digit run for fictional values."""
    def word(m):
        w = m.group(0)
        rep = mapping.get(w.upper())
        if not rep:
            return w
        return rep.upper() if w.isupper() else rep.title() if w[0].isupper() else rep.lower()
    line = re.sub(r'[A-Za-z]+', word, line)
    return re.sub(r'\d+', lambda m: str((int(m.group(0)) * 7 + 3) % (10 ** len(m.group(0)))).zfill(len(m.group(0))), line)


def surfaces_from_run(root: Path, overrides: dict[str, str] | None = None) -> tuple[list[dict], list[dict], dict[str, str]]:
    """Split redact regions into text surfaces (with OCR template rows) and covers."""
    red = json.loads((root / 'redact.json').read_text())
    ver = json.loads((root / 'verify.json').read_text()) if (root / 'verify.json').exists() else {'results': []}
    rows_by_track = {r['track_id']: r for r in ver['results'] if r['status'] == 'verified' and r.get('ocr_text')}
    texts, covers, idents, all_claims = [], [], [], []
    for reg in red['regions']:
        v = rows_by_track.get(reg['track_id'])
        if v:
            rows = list(dict.fromkeys(v['ocr_text']))  # OCR rows, de-duplicated, in reading order
            claims = v.get('claimed') or []
            texts.append({**reg, 'rows': rows, 'claims': claims})
            all_claims += claims
            idents += identifying_words(claims)
        else:
            covers.append(reg)
    def is_ident(w):
        return any(SequenceMatcher(None, w.upper(), i.upper()).ratio() >= RATIO for i in idents)
    words = []
    for t in texts:
        for row in t['rows']:
            ws = re.findall(r'[A-Za-z]{3,}', row)
            for k, w in enumerate(ws):
                if len(w) >= 4 and is_ident(w):
                    # a Capitalized word right before an identified surname is a given name ("Rohan Kulkarni")
                    if k > 0 and ws[k - 1][0].isupper() and not is_ident(ws[k - 1]) and ws[k - 1].upper() not in {'THE', 'FROM'}:
                        words.append(ws[k - 1])
                        all_claims.append(f'{ws[k - 1]} {w}')
                    words.append(w)
    return texts, covers, build_mapping(words, all_claims, overrides)


def _ink(crop: np.ndarray) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Background = median of the crop border; ink = median of the pixels farthest from it."""
    border = np.concatenate([crop[:3].reshape(-1, 3), crop[-3:].reshape(-1, 3), crop[:, :3].reshape(-1, 3), crop[:, -3:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    d = np.linalg.norm(crop.reshape(-1, 3).astype(float) - bg, axis=1)
    ink = np.median(crop.reshape(-1, 3)[d >= np.percentile(d, 92)], axis=0)
    return tuple(int(x) for x in bg), tuple(int(x) for x in ink)


def _mode(px: np.ndarray) -> tuple[int, int, int]:
    q = (px // 24).astype(np.int32)
    keys = q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    k = vals[np.argmax(counts)]
    sel = px[keys == k]
    return tuple(int(x) for x in np.median(sel, axis=0))


def render_rows(frame: np.ndarray, inner, layout: list[tuple[str, list[float]]], mapping: dict[str, str]) -> int:
    """Repaint only the OCR rows whose text changes, inside the un-padded surface `inner` (x1, y1, x2, y2).
    Background = dominant colour of a thin ring around the row; ink = dominant colour of the row's high-contrast pixels."""
    x1, y1, x2, y2 = inner
    bw, bh = x2 - x1, y2 - y1
    if bw < 8 or bh < 8:
        return 0
    n = 0
    for text, (nx1, ny1, nx2, ny2) in layout:
        new = rewrite(text, mapping)
        if new == text:
            continue
        rx1, ry1 = int(x1 + nx1 * bw) - 2, int(y1 + ny1 * bh) - 2
        rx2, ry2 = int(x1 + nx2 * bw) + 3, int(y1 + ny2 * bh) + 3
        rx1, ry1, rx2, ry2 = max(x1, rx1), max(y1, ry1), min(x2, rx2), min(y2, ry2)
        if rx2 - rx1 < 4 or ry2 - ry1 < 4:
            continue
        ring = np.concatenate([frame[max(y1, ry1 - 3):ry1, rx1:rx2].reshape(-1, 3), frame[ry2:min(y2, ry2 + 3), rx1:rx2].reshape(-1, 3),
                               frame[ry1:ry2, max(x1, rx1 - 3):rx1].reshape(-1, 3), frame[ry1:ry2, rx2:min(x2, rx2 + 3)].reshape(-1, 3)])
        row = frame[ry1:ry2, rx1:rx2].reshape(-1, 3)
        bg = _mode(ring if len(ring) else row)
        d = np.linalg.norm(row.astype(float) - np.array(bg, float), axis=1)
        ink = _mode(row[d >= np.percentile(d, 85)])
        rh = ry2 - ry1
        img = Image.new('RGB', (rx2 - rx1 + 60, rh), bg[::-1])
        dr = ImageDraw.Draw(img)
        size = max(8, int(rh * 0.82))
        f = _font(size, bold=True)
        while size > 8 and dr.textlength(new, font=f) > (x2 - rx1) - 4:
            size -= 1
            f = _font(size, bold=True)
        dr.text((2, (rh - size) / 2 - size * 0.12), new, fill=ink[::-1], font=f)
        tw = int(dr.textlength(new, font=f)) + 6
        w_fill = max(rx2 - rx1, min(tw, x2 - rx1))
        frame[ry1:ry2, rx1:rx1 + w_fill] = np.array(img)[:, :w_fill, ::-1]
        n += 1
    return n


def run(root: Path, ocr_rows: OcrRows, audit_fps: float = 2.0, overrides: dict[str, str] | None = None) -> dict:
    texts, covers, mapping = surfaces_from_run(root, overrides)
    pad = int(json.loads((root / 'redact.json').read_text()).get('pad_px', 0))
    cap = cv2.VideoCapture(str(root / 'input.mp4'))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = []
    while True:
        ok, img = cap.read()
        if not ok:
            break
        frames.append(img)
    cap.release()
    h, w = frames[0].shape[:2]
    idents = sorted({k for k in mapping})

    # per frame: merge overlapping text-surface boxes, each with the template of its first track
    def surfaces_at(fi):
        out = []
        for t in texts:
            for fr in t['frames']:
                if fr['frame_idx'] == fi:
                    box = fr['box']
                    for s in out:
                        if _iou(s['box'], box) >= MERGE_IOU:
                            break
                    else:
                        out.append({'box': box, 'rows': t['rows']})
                    break
        return out

    def covers_at(fi):
        return [fr['box'] for c in covers for fr in c['frames'] if fr['frame_idx'] == fi]

    # one OCR pass per distinct surface template to get row boxes (normalized to the un-padded surface)
    layouts: dict[tuple, list] = {}
    lay_dir = root / 'natural_layout'
    lay_dir.mkdir(exist_ok=True)
    for t in texts:
        key = tuple(t['rows'])
        if key in layouts or not t['frames']:
            continue
        fr = t['frames'][len(t['frames']) // 2]
        x1, y1, x2, y2 = [int(v) for v in fr['box']]
        crop = frames[fr['frame_idx']][y1 + pad + 2:y2 - pad - 2, x1 + pad + 2:x2 - pad - 2]
        if crop.size == 0:
            continue
        cp = lay_dir / f"layout_{len(layouts)}.jpg"
        cv2.imwrite(str(cp), crop)
        layouts[key] = [(r['text'], r['box']) for r in ocr_rows([(0, cp)], crop.shape[1], crop.shape[0])]

    fallback: set[tuple[int, int]] = set()  # (frame_idx, surface index) rendered as a cover after the audit

    def render_all():
        out = []
        for fi, img in enumerate(frames):
            f = img.copy()
            holes = []  # boxes to blank with an opaque cover
            for si, s in enumerate(surfaces_at(fi)):
                if (fi, si) in fallback:
                    holes.append(s['box'])
                else:
                    x1, y1, x2, y2 = [int(v) for v in s['box']]
                    inner = (x1 + pad + 2, y1 + pad + 2, x2 - pad - 2, y2 - pad - 2)
                    lay = layouts.get(tuple(s['rows']))
                    if lay:
                        render_rows(f, inner, lay, mapping)
                    else:  # no row layout: redraw the whole surface
                        render_surface(f, s['box'], [rewrite(r, mapping) for r in s['rows']], inset=pad + 2)
            here = [sf['box'] for sf in surfaces_at(fi)]
            for cb in covers_at(fi):
                # a cover on the same physical surface as a re-rendered text surface is superseded by it (audit still checks)
                if any(_iou(cb, b) >= MERGE_IOU for b in here):
                    continue
                holes.append(cb)
            for x1, y1, x2, y2 in holes:
                f[max(0, int(y1)):int(y2), max(0, int(x1)):int(x2)] = 0
            out.append(f)
        return out

    def audit(rendered):
        tmp = root / 'natural_audit'
        tmp.mkdir(exist_ok=True)
        step = max(1, int(round(fps / audit_fps)))
        samples = []
        for fi in range(0, len(rendered), step):
            p = tmp / f'n_{fi:05d}.jpg'
            cv2.imwrite(str(p), rendered[fi])
            samples.append((int(fi / fps * 1000), p))
        rows = ocr_rows(samples, w, h)
        resid = []
        for r in rows:
            for word in re.findall(r'[A-Za-z]{4,}', r['text']):
                if any(SequenceMatcher(None, word.upper(), i).ratio() >= RATIO for i in idents):
                    resid.append({'time_ms': r['time_ms'], 'text': r['text']})
        return samples, rows, resid

    rendered = render_all()
    samples, rows, resid = audit(rendered)
    passes = 1
    if resid:  # fall back to covers on surfaces present in frames within 0.5 s of a residual, then re-audit once
        for r in resid:
            fi0 = int(r['time_ms'] / 1000 * fps)
            for fi in range(max(0, fi0 - int(fps / 2)), min(len(frames), fi0 + int(fps / 2) + 1)):
                for si in range(len(surfaces_at(fi))):
                    fallback.add((fi, si))
        rendered = render_all()
        samples, rows, resid = audit(rendered)
        passes = 2
    out = root / 'output_natural.mp4'
    proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-',
                             '-i', str(root / 'output.mp4'), '-map', '0:v', '-map', '1:a?', '-c:v', 'libx264', '-preset', 'veryfast',
                             '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-shortest', str(out)], stdin=subprocess.PIPE)
    for f in rendered:
        proc.stdin.write(f.tobytes())
    proc.stdin.close()
    proc.wait()
    replacements = sorted({(r, rewrite(r, mapping)) for t in texts for r in t['rows'] if rewrite(r, mapping) != r})
    surface_frames = sum(len(surfaces_at(fi)) for fi in range(len(frames)))
    report = {
        'stage': 'natural_text', 'output': out.name, 'mapping': mapping, 'user_overrides': sorted((overrides or {}).items()),
        'replacements': [{'original': a, 'fictional': b} for a, b in replacements],
        'text_surface_frames': surface_frames, 'fallback_cover_frames': len(fallback), 'cover_regions': len(covers),
        'audit': {'sampled_frames': len(samples), 'ocr_rows': len(rows), 'residual_original_words': resid, 'passes': passes,
                  'status': 'COVERED' if not resid else 'UNRESOLVED',
                  'check': 'local OCR on sampled natural-export frames must not read any original identifying word (fuzzy >= 0.8)'},
        'note': 'Replacement text is fictional (built-in pool or user-chosen). Faces, plates and masks without verified text keep opaque covers.',
    }
    (root / 'natural.json').write_text(json.dumps(report, indent=1, ensure_ascii=False))
    return report
