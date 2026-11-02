"""Still-image erase: Muse Image removes what Veil found, the result is pasted back ONLY inside the found regions, and
deterministic code re-checks the output. Muse Image edits by instruction (it has no mask parameter, docs: dev.meta.ai/docs/image-generation),
so every target is described by label and position, and nothing outside the boxes is taken from the model."""
import base64
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

GROW = 8          # px the paste mask extends past each box (the model's fill needs room to blend)
FEATHER = 2       # px Gaussian feather on the paste edge
MIN_CHANGE = 12.0 # mean abs pixel change a box must show, else the model did not remove it
RATIO = 0.8       # fuzzy match for residual identifying words (same as natural_text)

Edit = Callable[[bytes, str], np.ndarray]  # (png bytes, prompt) -> BGR image (any size)
OcrRows = Callable[[list, int, int], list[dict]]


class Target(BaseModel):
    model_config = ConfigDict(extra='forbid')
    box: tuple[int, int, int, int]
    label: str = Field(min_length=1)


def _where(box, w, h) -> str:
    cx, cy = (box[0] + box[2]) / 2 / w, (box[1] + box[3]) / 2 / h
    v = 'top' if cy < 0.34 else 'bottom' if cy > 0.66 else 'middle'
    hz = 'left' if cx < 0.34 else 'right' if cx > 0.66 else 'center'
    return f'{v}-{hz}' if (v, hz) != ('middle', 'center') else 'center'


def build_prompt(targets: list[Target], size: tuple[int, int]) -> str:
    w, h = size
    items = '; '.join(f'the {t.label} at the {_where(t.box, w, h)}' for t in targets)
    return (f'Remove these overlays or objects: {items}. Fill each area with the natural scene that would be behind it '
            'so it looks untouched. Keep everything else exactly unchanged.')


def _mask(shape, targets, grow) -> np.ndarray:
    h, w = shape[:2]
    m = np.zeros((h, w), np.uint8)
    for t in targets:
        x1, y1, x2, y2 = t.box
        m[max(0, y1 - grow):min(h, y2 + grow), max(0, x1 - grow):min(w, x2 + grow)] = 255
    return m


def erase(image: np.ndarray, targets: list[Target], edit: Edit, ocr_rows: OcrRows, identifiers: list[str], work: Path) -> tuple[np.ndarray, dict]:
    h, w = image.shape[:2]
    if not targets:
        raise ValueError('no targets to erase')
    for t in targets:
        x1, y1, x2, y2 = t.box
        if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
            raise ValueError(f'box {t.box} is outside the {w}x{h} image')
    work.mkdir(parents=True, exist_ok=True)
    src = work / 'erase_in.png'
    cv2.imwrite(str(src), image)
    prompt = build_prompt(targets, (w, h))
    gen = edit(src.read_bytes(), prompt)
    gen = cv2.resize(gen, (w, h), interpolation=cv2.INTER_AREA)
    a = (cv2.GaussianBlur(_mask(image.shape, targets, GROW), (0, 0), FEATHER) / 255.0)[..., None]
    out = (gen * a + image * (1 - a)).astype(np.uint8)
    cv2.imwrite(str(work / 'erase_out.png'), out)

    reasons, changes = [], []
    for t in targets:
        x1, y1, x2, y2 = t.box
        c = float(np.abs(out[y1:y2, x1:x2].astype(float) - image[y1:y2, x1:x2].astype(float)).mean())
        changes.append({'label': t.label, 'box': list(t.box), 'mean_change': round(c, 1)})
        if c < MIN_CHANGE:
            reasons.append(f'region "{t.label}" has not changed (mean change {c:.1f} < {MIN_CHANGE:.0f}); the model may have ignored the instruction')
    idents = sorted({i.upper() for i in identifiers if i.strip()})
    rows = ocr_rows([(0, work / 'erase_out.png')], w, h) if idents else []
    resid = [r['text'] for r in rows for word in re.findall(r'[A-Za-z]{4,}', r['text'])
             if any(SequenceMatcher(None, word.upper(), i).ratio() >= RATIO for i in idents)]
    if resid:
        reasons.append('an identifying word is still readable in the output')
    status = 'UNRESOLVED' if reasons else 'COVERED' if idents else 'NOT_CHECKED'
    rep = {'stage': 'erase_image', 'status': status, 'reasons': reasons, 'prompt': prompt, 'regions': changes,
           'residual_words': resid, 'identifiers_checked': idents,
           'check': 'each box must change; local OCR on the output must not read any listed identifying word (fuzzy >= 0.8)'
                    if idents else 'no identifiers given: OCR check not run',
           'note': 'Muse Image regenerates the whole frame; only the pixels inside the boxes (+8 px feather) are used. '
                   'The fill is generated, not recovered: it is not evidence of what was behind the object.'}
    return out, rep


def make_muse_edit(client, ledger, name_prefix: str = 'erase-image') -> Edit:
    """Hosted Muse Image edit (/v1/images/edits). Each call is reserved in the ledger first; no automatic retry."""
    n = [0]

    def edit(png: bytes, prompt: str) -> np.ndarray:
        import io
        name = f'{name_prefix}-{n[0]}'; n[0] += 1
        start = ledger.begin(name, 'muse-image-1.0', '/v1/images/edits', '1 image (PNG) sent to Meta')
        try:
            f = io.BytesIO(png); f.name = 'image.png'
            r = client.images.edit(model='muse-image-1.0', image=f, n=1, response_format='b64_json', prompt=prompt)
            out = cv2.imdecode(np.frombuffer(base64.b64decode(r.data[0].b64_json), np.uint8), cv2.IMREAD_COLOR)
            ledger.finish(name, start, estimated_usd=0.01)
            return out
        except Exception as exc:
            ledger.fail(name, start, exc)
            raise
    return edit
