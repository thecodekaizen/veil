"""Phase 3 (record_myself): clean, check and stitch recorded VO lines.

Input:  voice/raw/line_<id>.(webm|wav|m4a|mp3)   one file per script line (latest file wins)
Output: voice/clean/line_<id>.wav, voice/vo.wav (-16 LUFS, -1.5 dBTP), voice/report.json, voice/review.html,
        timing/words.json (word timestamps of vo.wav, input to phase 4)
Run:    .venv/bin/python process_voice.py [--allow-missing]
Checks: per-line WER vs script <= 5%, no clipping, no internal silence > 700 ms; final vo.wav WER < 3%.
"""
import argparse
import html
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
SR = 48000
MODEL = 'mlx-community/whisper-large-v3-turbo'
CLEAN = 'highpass=f=80,afftdn=nf=-25,acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2,deesser=i=0.4'
CLEAN_SYNTH = 'highpass=f=60,acompressor=threshold=-18dB:ratio=2:attack=5:release=80'  # generated takes: no denoise/de-ess
MAX_PAUSE_S = 0.45  # internal pauses longer than this are shortened (keeps pace; never removes speech)
NUM = {'0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five', '6': 'six', '7': 'seven',
       '8': 'eight', '9': 'nine', '.': ' point '}
SAME = {'okay': 'ok', "weren't": 'werent', "that's": 'thats', "didn't": 'didnt', 'labelled': 'labeled'}
# Product names and terms the script uses, given to Whisper as context (spelling only, not content).
VOCAB = 'Veil. Muse Spark. SAM 3.1. Muse Voice Transcribe. OCR. Re-reads. Post-gate. Kulkarni.'


def norm(text: str) -> list[str]:
    t = text.lower().replace('—', ' ').replace('re-read', 'reread').replace('-', ' ')
    t = re.sub(r'\d+(?:\.\d+)?', lambda m: ' '.join(NUM[c] for c in m.group()), t)
    toks = re.findall(r"[a-z']+", t)
    return [SAME.get(w, w.replace("'", '')) for w in toks]


def wer(ref: list[str], hyp: list[str]) -> tuple[float, list[str]]:
    d = np.zeros((len(ref) + 1, len(hyp) + 1), int)
    d[:, 0], d[0, :] = range(len(ref) + 1), range(len(hyp) + 1)
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    missing = [w for w in ref if w not in hyp]
    return float(d[-1, -1] / max(1, len(ref))), missing


def ff(*args, level='error'):
    return subprocess.run(['ffmpeg', '-hide_banner', '-v', level, '-y', *args], check=True, capture_output=True, text=True)


def read(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def write(path: Path, x: np.ndarray):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def transcribe(path: Path) -> dict:
    import mlx_whisper
    return mlx_whisper.transcribe(str(path), path_or_hf_repo=MODEL, word_timestamps=True, language='en', initial_prompt=VOCAB,
                                  condition_on_previous_text=False)


def internal_silences(x: np.ndarray, min_s=0.7, thr_db=-45) -> list[float]:
    hop = SR // 100
    n = len(x) // hop
    db = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    voiced = np.flatnonzero(db > thr_db)
    if len(voiced) == 0:
        return []
    gaps = np.diff(voiced) / 100
    return [round(float(g), 2) for g in gaps if g > min_s]


def cap_pauses(x: np.ndarray, max_s=MAX_PAUSE_S, thr_db=-45) -> np.ndarray:
    hop = SR // 100
    n = len(x) // hop
    db = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    keep = np.ones(n, bool)
    run = 0
    for i in range(n):
        run = run + 1 if db[i] <= thr_db else 0
        if run > max_s * 100:
            keep[i] = False
    out = np.concatenate([x[i * hop:(i + 1) * hop] for i in range(n) if keep[i]] + [x[n * hop:]])
    return out


def trim(x: np.ndarray, thr_db=-45, keep_s=0.05) -> np.ndarray:
    hop = SR // 100
    n = len(x) // hop
    db = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    v = np.flatnonzero(db > thr_db)
    if len(v) == 0:
        return x
    a, b = max(0, v[0] * hop - int(keep_s * SR)), min(len(x), (v[-1] + 1) * hop + int(keep_s * SR))
    return x[a:b]


def room_tone(raws: list[np.ndarray], seconds=0.4) -> np.ndarray:
    """Quietest `seconds` window across the recordings (their own room noise), not digital silence."""
    w = int(seconds * SR)
    best, best_e = None, np.inf
    for x in raws:
        for s in range(0, max(1, len(x) - w), SR // 20):
            seg = x[s:s + w]
            e = float((seg ** 2).mean()) if len(seg) == w else np.inf
            if e < best_e:
                best, best_e = seg, e
    return best if best is not None else np.zeros(w, np.float32)


def loop_to(tone: np.ndarray, n: int) -> np.ndarray:
    reps = int(np.ceil(n / len(tone))) + 1
    t = np.concatenate([tone, tone[::-1]] * reps)[:n]
    return t


def fade(x: np.ndarray, ms=10) -> np.ndarray:
    k = min(len(x) // 2, int(SR * ms / 1000))
    r = np.linspace(0, 1, k, dtype=np.float32)
    x = x.copy(); x[:k] *= r; x[-k:] *= r[::-1]
    return x


def last_json(text: str) -> dict:
    return json.loads(re.findall(r'\{[^{}]*\}', text)[-1])


def loudnorm(src: Path, dst: Path) -> dict:
    p = ff('-i', str(src), '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-', level='info')
    m = last_json(p.stderr)
    ff('-i', str(src), '-af', f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
       f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true",
       '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s16le', str(dst))
    q = ff('-i', str(dst), '-af', 'loudnorm=I=-16:TP=-1.5:print_format=json', '-f', 'null', '-', level='info')
    o = last_json(q.stderr)
    return {'integrated_lufs': float(o['input_i']), 'true_peak_dbtp': float(o['input_tp']), 'lra': float(o['input_lra'])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--allow-missing', action='store_true', help='stitch only the lines present (draft timing)')
    a = ap.parse_args()
    plan = json.loads((ROOT / 'plan.json').read_text())
    raw_dir, clean_dir = ROOT / 'voice/raw', ROOT / 'voice/clean'
    clean_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / 'timing').mkdir(exist_ok=True)
    report, pieces, raws, problems = [], [], [], []
    for line in plan['script']:
        cands = sorted(raw_dir.glob(f"line_{line['id']}.*"), key=lambda p: p.stat().st_mtime)
        if not cands:
            problems.append(f"{line['id']}: no recording")
            report.append({'id': line['id'], 'status': 'missing'})
            continue
        src, dec, out = cands[-1], clean_dir / f"line_{line['id']}.raw.wav", clean_dir / f"line_{line['id']}.wav"
        ff('-i', str(src), '-ac', '1', '-ar', str(SR), '-c:a', 'pcm_s16le', str(dec))
        x = read(dec)
        raws.append(x)
        peak = float(np.abs(x).max())
        synth = src.suffix == '.wav'  # generated takes are copied in as .wav; mic recordings arrive as .webm
        ff('-i', str(dec), '-af', CLEAN_SYNTH if synth else CLEAN, '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_s16le', str(out))
        y = cap_pauses(trim(read(out)))
        write(out, y)
        hyp = transcribe(out)['text']
        e, missing = wer(norm(line['text']), norm(hyp))
        gaps = internal_silences(y)
        flags = (['clipping'] if peak >= 0.999 else []) + ([f'silence {gaps} s'] if gaps else []) + \
                ([f'WER {e:.0%} > 5%'] if e > 0.05 else []) + ([f'missing {missing}'] if missing else [])
        if flags:
            problems.append(f"{line['id']}: {'; '.join(flags)}")
        report.append({'id': line['id'], 'file': src.name, 'duration_s': round(len(y) / SR, 2), 'peak': round(peak, 3),
                       'wer': round(e, 3), 'heard': hyp.strip(), 'flags': flags, 'status': 'ok' if not flags else 'check'})
        pieces.append((line, y))
    if not pieces:
        sys.exit('no recordings in voice/raw/')
    if problems and not a.allow_missing:
        print('\n'.join(problems))
    tone = room_tone(raws)
    seq = [loop_to(tone, int(0.15 * SR))]
    offsets, pos = [], len(seq[0])
    for line, y in pieces:
        offsets.append({'id': line['id'], 'start_s': round(pos / SR, 3), 'end_s': round((pos + len(y)) / SR, 3)})
        gap = loop_to(tone, int(line['pause_after_ms'] / 1000 * SR))
        seq += [fade(y), gap]
        pos += len(y) + len(gap)
    vo = np.concatenate(seq)
    (ROOT / 'timing/lines.json').write_text(json.dumps(offsets, indent=1))  # exact: computed while stitching
    vo = vo + loop_to(tone, len(vo)) * 0.5  # low room-tone bed under everything so gaps never go dead
    stitched = ROOT / 'voice/vo.stitched.wav'
    write(stitched, vo)
    loud = loudnorm(stitched, ROOT / 'voice/vo.wav')
    full = transcribe(ROOT / 'voice/vo.wav')
    words = [{'word': w['word'].strip(), 'start': round(w['start'], 3), 'end': round(w['end'], 3)}
             for s in full['segments'] for w in s.get('words', [])]
    (ROOT / 'timing/words.json').write_text(json.dumps(words, indent=1))
    ref = norm(' '.join(l['text'] for l, _ in pieces))
    total_wer, total_missing = wer(ref, norm(full['text']))
    summary = {'lines': report, 'recorded': len(pieces), 'of': len(plan['script']), 'loudness': loud,
               'vo_duration_s': round(len(vo) / SR, 2), 'vo_wer': round(total_wer, 4), 'vo_missing_words': total_missing,
               'pass': total_wer < 0.03 and not problems and len(pieces) == len(plan['script'])}
    (ROOT / 'voice/report.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    def player(r):
        return '—' if r['status'] == 'missing' else f"<audio controls src='clean/line_{r['id']}.wav'></audio>"
    rows = ''.join(f"<tr><td>{r['id']}</td><td>{player(r)}</td>"
                   f"<td>{html.escape(r.get('heard', ''))}</td><td>{r.get('wer', '')}</td><td>{html.escape('; '.join(r.get('flags', [])) or r['status'])}</td></tr>"
                   for r in report)
    (ROOT / 'voice/review.html').write_text(
        f"<!doctype html><meta charset=utf-8><title>VO Review</title><style>body{{background:#0d0f12;color:#eee;font:14px system-ui;padding:20px}}"
        f"td{{border-top:1px solid #333;padding:6px;vertical-align:top}}</style><h1>VO review</h1>"
        f"<p>Full VO: <audio controls src='vo.wav'></audio> {summary['vo_duration_s']} s · {loud['integrated_lufs']} LUFS · "
        f"TP {loud['true_peak_dbtp']} dBTP · WER {total_wer:.1%}</p><table><tr><th>id</th><th>take</th><th>Whisper heard</th><th>WER</th><th>flags</th></tr>{rows}</table>")
    print(json.dumps({k: v for k, v in summary.items() if k != 'lines'}, indent=1))
    if problems:
        print('needs attention:\n  ' + '\n  '.join(problems))


if __name__ == '__main__':
    main()
