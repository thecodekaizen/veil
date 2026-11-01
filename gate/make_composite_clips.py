"""Build the composited gate clips c1-c3: licensed Commons footage (gate/exploratory/SOURCES.md) + planted FICTIONAL leaks.

Usage: uv run --project veil python -m gate.make_composite_clips
Writes gate/clips/c{1,2,3}.mp4 (gitignored; regenerate with this script) and gate/labels/c{1,2,3}.json (committed BEFORE any model run).
Everything planted is fictional (CLAUDE.md allowlist values). Labels are exact because we draw the leaks; they are eval-only.
Deviation from GATE.md's "staged set": planted graphics are composited on found footage, and the spoken number is Hindi TTS (macOS
'Lekha'), not a person speaking. Recorded in docs/decisions.md. Re-running refuses to overwrite existing labels.
"""
import hashlib
import json
import subprocess
import wave
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 960, 540, 25, 25
SRC = Path('gate/exploratory')
OUT_CLIPS, OUT_LABELS = Path('gate/clips'), Path('gate/labels')
BOLD, MONO = '/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/System/Library/Fonts/Menlo.ttc'
DIGITS = '9876543210'  # fictional 98765 43210
DEVA = ['नौ', 'आठ', 'सात', 'छह', 'पाँच', 'चार', 'तीन', 'दो', 'एक', 'शून्य']  # 9 8 7 6 5 4 3 2 1 0
PREFIX_TEXT, NUMBER_TEXT = 'मेरा फ़ोन नंबर है', ' '.join(DEVA)


def font(path, size):
    return ImageFont.truetype(path, size)


def run(*a):
    subprocess.run(list(map(str, a)), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


# ---- planted items: each returns an RGBA layer (W x H) and its pixel box (x, y, w, h) ----
def layer():
    return Image.new('RGBA', (W, H), (0, 0, 0, 0))


def delivery_box(x=40, y=372):
    im = layer(); d = ImageDraw.Draw(im); w, h = 230, 150
    d.rectangle((x, y, x + w, y + h), fill=(176, 130, 82), outline=(110, 78, 45), width=3)
    d.rectangle((x + 14, y + 22, x + w - 14, y + 112), fill=(250, 250, 244), outline=(60, 60, 60), width=1)
    for i, t in enumerate(['TO: Rohan Kulkarni', 'Flat 12, Sunshine CHS', 'Fakepur 400099']):
        d.text((x + 22, y + 32 + i * 26), t, font=font(MONO, 15), fill=(15, 15, 15))
    return im, (x, y, w, h)


def society_board(x=620, y=40):
    im = layer(); d = ImageDraw.Draw(im); w, h = 320, 70
    d.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=(22, 74, 52), outline=(235, 235, 225), width=3)
    d.text((x + 14, y + 22), 'SUNSHINE CHS — WING B', font=font(BOLD, 22), fill=(245, 245, 235))
    return im, (x, y, w, h)


def notification(x=280, y=28):
    im = layer(); d = ImageDraw.Draw(im); w, h = 400, 92
    d.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=(236, 238, 242), outline=(180, 184, 192), width=2)
    d.rounded_rectangle((x + 14, y + 16, x + 62, y + 64), radius=11, fill=(52, 168, 83))
    d.text((x + 76, y + 14), 'Messages · now', font=font(BOLD, 14), fill=(110, 112, 120))
    d.text((x + 76, y + 36), 'Rohan Kulkarni', font=font(BOLD, 22), fill=(20, 20, 24))
    d.text((x + 76, y + 64), 'Your parcel is at the gate', font=font(BOLD, 15), fill=(70, 72, 80))
    return im, (x, y, w, h)


def nameplate(x=680, y=392):
    im = layer(); d = ImageDraw.Draw(im); w, h = 250, 64
    d.rectangle((x, y, x + w, y + h), fill=(30, 28, 26), outline=(190, 160, 90), width=3)
    d.text((x + 16, y + 18), 'KULKARNI — 12', font=font(BOLD, 25), fill=(222, 190, 110))
    return im, (x, y, w, h)


def logo(x=40, y=40):
    im = layer(); d = ImageDraw.Draw(im); w, h = 130, 130
    d.ellipse((x, y, x + w, y + h), fill=(200, 40, 70), outline=(255, 255, 255), width=4)
    d.text((x + 18, y + 48), 'ZENITH', font=font(BOLD, 27), fill=(255, 255, 255))
    return im, (x, y, w, h)


def code_editor(x=40, y=330):
    im = layer(); d = ImageDraw.Draw(im); w, h = 330, 170
    d.rectangle((x, y, x + w, y + h), fill=(30, 33, 40), outline=(90, 94, 104), width=2)
    for i, t in enumerate(['def total(items):', '    s = 0', '    for i in items:', '        s += i.price', '    return s']):
        d.text((x + 14, y + 14 + i * 28), t, font=font(MONO, 17), fill=(170, 220, 160))
    return im, (x, y, w, h)


def book_cover(x=700, y=300):
    im = layer(); d = ImageDraw.Draw(im); w, h = 150, 210
    d.rectangle((x, y, x + w, y + h), fill=(40, 70, 130), outline=(240, 240, 240), width=3)
    d.text((x + 14, y + 40), 'THE', font=font(BOLD, 24), fill=(240, 230, 190))
    d.text((x + 14, y + 74), 'LONG', font=font(BOLD, 24), fill=(240, 230, 190))
    d.text((x + 14, y + 108), 'RIVER', font=font(BOLD, 24), fill=(240, 230, 190))
    return im, (x, y, w, h)


# ---- audio ----
def tts(text, path):
    run('say', '-v', 'Lekha', '-o', path, '--data-format=LEI16@24000', text)


def read_wav(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768, w.getframerate()


def speech_span(x, rate, thr=0.01):
    idx = np.where(np.abs(x) > thr)[0]
    return idx[0] / rate, idx[-1] / rate


# ---- clip builder ----
CLIPS = {
    'c1': dict(src='cuttack.webm', ss=20, items=[('L1', 'visual', 'delivery box with an address label', True, delivery_box, (2, 22)),
                                                  ('L4', 'visual', 'society name board', False, society_board, (3, 24))],
               controls=[('C1', 'product logo badge', logo, (1, 24))], audio=False),
    'c2': dict(src='delhi.webm', ss=5, items=[('L2', 'visual', 'phone notification showing a name', True, notification, (4, 15)),
                                              ('L3', 'visual', 'door nameplate', False, nameplate, (2, 24))],
               controls=[('C2', 'code in an editor', code_editor, (1, 24))], audio=False),
    'c3': dict(src='cuttack.webm', ss=60, items=[], controls=[('C3', 'book cover', book_cover, (1, 24))], audio=True),
}


def build(cid, spec, tmp: Path):
    base = tmp / f'{cid}_base.mp4'
    run('ffmpeg', '-y', '-ss', spec['ss'], '-t', DUR, '-i', SRC / spec['src'], '-vf', f'scale={W}:{H},fps={FPS}', '-c:v', 'libx264',
        '-preset', 'veryfast', '-crf', '16', '-pix_fmt', 'yuv420p', '-an', base)
    planted = [(i[0], i[4], i[5]) for i in spec['items']] + [(c[0], c[2], c[3]) for c in spec['controls']]
    layers = [(pid, *fn(), rng) for pid, fn, rng in planted]  # (id, RGBA, box, range)
    cap = cv2.VideoCapture(str(base)); silent = tmp / f'{cid}_silent.mp4'
    wr = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*'mp4v'), FPS, (W, H))
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = n / FPS
        im = None
        for pid, rgba, box, (a, b) in layers:
            if a <= t <= b:
                im = im or Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGBA')
                im = Image.alpha_composite(im, rgba)
        wr.write(cv2.cvtColor(np.array(im.convert('RGB')), cv2.COLOR_RGB2BGR) if im else frame)
        n += 1
    wr.release(); cap.release()
    # audio: ambient from the base footage; Hindi TTS number on c3 only
    amb = tmp / f'{cid}_amb.wav'
    run('ffmpeg', '-y', '-ss', spec['ss'], '-t', DUR, '-i', SRC / spec['src'], '-vn', '-ac', 1, '-ar', 24000, '-c:a', 'pcm_s16le', amb)
    audio_leak = None
    if spec['audio']:
        tts(PREFIX_TEXT, tmp / 'prefix.wav'); tts(NUMBER_TEXT, tmp / 'number.wav')
        px, rate = read_wav(tmp / 'prefix.wav'); nx, _ = read_wav(tmp / 'number.wav'); ax, _ = read_wav(amb)
        start = 8.0; gap = 0.25
        mix = ax[:DUR * rate].copy()
        mix = np.pad(mix, (0, max(0, DUR * rate - len(mix))))
        o1 = int(start * rate); mix[o1:o1 + len(px)] += px
        o2 = o1 + len(px) + int(gap * rate); mix[o2:o2 + len(nx)] += nx
        s, e = speech_span(nx, rate)
        audio_leak = dict(t_start=round(o2 / rate + s, 3), t_end=round(o2 / rate + e, 3))
        mix = np.clip(mix, -1, 1)
        with wave.open(str(amb), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    out = OUT_CLIPS / f'{cid}.mp4'
    run('ffmpeg', '-y', '-i', silent, '-i', amb, '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '96k', '-shortest', '-map_metadata', '-1', out)
    return out, layers, audio_leak


def labels_for(cid, spec, out, layers, audio_leak):
    box_of = {pid: (box, rng) for pid, _, box, rng in layers}

    def refs(pid):
        (x, y, w, h), (a, b) = box_of[pid]
        return [{'t_s': round(a + (b - a) * f, 2), 'x': x, 'y': y, 'w': w, 'h': h} for f in (0.2, 0.5, 0.8)]
    leaks = [{'leak_id': pid, 'kind': kind, 'concept': concept, 'in_baseline': inb, 'visible_ranges': [list(box_of[pid][1])],
              'ref_boxes': refs(pid), 'audio': None} for pid, kind, concept, inb, _, _ in spec['items']]
    if audio_leak:
        leaks.append({'leak_id': 'A1', 'kind': 'audio', 'concept': 'spoken 10-digit phone number (Hindi digit words)', 'in_baseline': False,
                      'visible_ranges': [], 'ref_boxes': [], 'audio': {'text': NUMBER_TEXT, 'digits': DIGITS, **audio_leak}})
    controls = [{'control_id': pid, 'description': d, 'visible_ranges': [list(box_of[pid][1])], 'ref_boxes': refs(pid)} for pid, d, _, _ in spec['controls']]
    return {'clip_id': cid, 'clip_sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'fps': FPS, 'leaks': leaks, 'safe_controls': controls}


def main():
    from gate.labels_schema import Labels
    OUT_CLIPS.mkdir(parents=True, exist_ok=True); OUT_LABELS.mkdir(parents=True, exist_ok=True)
    if any((OUT_LABELS / f'{c}.json').exists() for c in CLIPS):
        raise SystemExit('refusing to overwrite committed labels (GATE.md: labels are written once)')
    tmp = Path('gate/clips/_tmp'); tmp.mkdir(parents=True, exist_ok=True)
    for cid, spec in CLIPS.items():
        out, layers, al = build(cid, spec, tmp)
        lab = labels_for(cid, spec, out, layers, al)
        Labels.model_validate(lab)
        (OUT_LABELS / f'{cid}.json').write_text(json.dumps(lab, indent=1) + '\n')
        print(cid, out, lab['clip_sha256'][:12], 'audio' if al else '')


if __name__ == '__main__':
    main()
