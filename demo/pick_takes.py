"""Pick the best generated take per line: Whisper WER vs script, no clipping, no internal silence > 700 ms,
then duration closest to 150 wpm. Winner -> voice/raw/line_<id>.wav; the creator's own recordings for those lines
move to voice/takes/user/. Writes voice/tts/picks.json.
Run: .venv/bin/python pick_takes.py [--dir voice/tts] [--only id,id]"""
import argparse
import json
import re
import shutil
from pathlib import Path

import numpy as np

from process_voice import SR, ff, internal_silences, norm, read, transcribe, trim, wer

ap = argparse.ArgumentParser()
ap.add_argument('--dir', default='voice/tts')
ap.add_argument('--only', default='')
a = ap.parse_args()
plan = json.loads(Path('plan.json').read_text())
only = set(filter(None, a.only.split(',')))
src = Path(a.dir)
picks_path = src / 'picks.json'
picks = json.loads(picks_path.read_text()) if picks_path.exists() else {}
for line in plan['script']:
    if only and line['id'] not in only:
        continue
    takes = sorted(src.glob(f"line_{line['id']}_*_t*.wav"))
    if not takes:
        continue
    target = len(norm(line['text'])) / 150 * 60
    scored = []
    for t in takes:
        tmp = src / f'.{t.stem}.48k.wav'
        ff('-i', str(t), '-ac', '1', '-ar', str(SR), '-c:a', 'pcm_s16le', str(tmp))
        x = trim(read(tmp))
        e, missing = wer(norm(line['text']), norm(transcribe(tmp)['text']))
        gaps = internal_silences(x)
        clip = float(np.abs(x).max()) >= 0.999
        dur = len(x) / SR
        ok = e <= 0.05 and not gaps and not clip
        scored.append({'take': t.name, 'wer': round(e, 3), 'missing': missing, 'gaps': gaps, 'clip': clip,
                       'duration_s': round(dur, 2), 'pace_err_s': round(abs(dur - target), 2), 'ok': ok})
        tmp.unlink()
    best = sorted(scored, key=lambda s: (not s['ok'], s['wer'], s['pace_err_s']))[0]
    picks[line['id']] = {'chosen': best['take'], 'all': scored}
    for own in Path('voice/raw').glob(f"line_{line['id']}.*"):
        shutil.move(str(own), f"voice/takes/user/{own.name}")
    shutil.copyfile(src / best['take'], f"voice/raw/line_{line['id']}.wav")
    print(f"{line['id']:4} {best['take']:28} wer {best['wer']:.2f} ok={best['ok']} {best['missing'] if best['missing'] else ''}")
picks_path.write_text(json.dumps(picks, indent=1))
