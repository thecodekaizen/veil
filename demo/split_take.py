"""Split one long VO take into per-line files by aligning Whisper word timestamps to the script.
Run: .venv/bin/python split_take.py voice/takes/<take> FIRST_ID [LAST_ID]   -> voice/raw/line_<id>.wav
Alignment: global edit-distance alignment of script tokens to heard tokens; each line starts at the first heard word
aligned to its first script tokens, and cuts land in the middle of the gap between words."""
import json, subprocess, sys
from pathlib import Path
import numpy as np
from process_voice import MODEL, VOCAB, norm

take, first = Path(sys.argv[1]), sys.argv[2]
plan = json.loads(Path('plan.json').read_text())
ids = [l['id'] for l in plan['script']]
last = sys.argv[3] if len(sys.argv) > 3 else ids[-1]
lines = plan['script'][ids.index(first):ids.index(last) + 1]
wav = take.with_suffix('.wav')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(take), '-ac', '1', '-ar', '48000', str(wav)], check=True)
import mlx_whisper
r = mlx_whisper.transcribe(str(wav), path_or_hf_repo=MODEL, word_timestamps=True, language='en', initial_prompt=VOCAB,
                           condition_on_previous_text=False)
heard = []  # (token, start, end)
for s in r['segments']:
    for w in s['words']:
        for t in norm(w['word']):
            heard.append((t, w['start'], w['end']))
ref, owner = [], []
for k, l in enumerate(lines):
    toks = norm(l['text']); ref += toks; owner += [k] * len(toks)
H = [h[0] for h in heard]
n, m = len(ref), len(H)
d = np.zeros((n + 1, m + 1), int); d[:, 0] = range(n + 1); d[0, :] = range(m + 1)
for i in range(1, n + 1):
    for j in range(1, m + 1):
        d[i, j] = min(d[i-1, j] + 1, d[i, j-1] + 1, d[i-1, j-1] + (ref[i-1] != H[j-1]))
i, j, match = n, m, {}
while i > 0 and j > 0:
    if d[i, j] == d[i-1, j-1] + (ref[i-1] != H[j-1]):
        match[i-1] = j-1; i, j = i-1, j-1
    elif d[i, j] == d[i-1, j] + 1:
        i -= 1
    else:
        j -= 1
starts = []
for k in range(len(lines)):
    js = [match[i] for i in range(len(ref)) if owner[i] == k and i in match]
    starts.append(min(js) if js else None)
dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(wav)]))
cuts = []
for k, j in enumerate(starts):
    if j is None:
        sys.exit(f'line {lines[k]["id"]} not found in take')
    cuts.append(0.0 if j == 0 else (heard[j-1][2] + heard[j][1]) / 2)
cuts.append(dur)
for k, l in enumerate(lines):
    out = Path('voice/raw') / f"line_{l['id']}.wav"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(wav), '-ss', f'{cuts[k]:.3f}', '-to', f'{cuts[k+1]:.3f}', str(out)], check=True)
    print(f"{l['id']:4} {cuts[k]:6.2f}-{cuts[k+1]:6.2f}  {' '.join(h[0] for h in heard if cuts[k] <= h[1] < cuts[k+1])[:80]}")
