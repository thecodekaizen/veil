"""Phase 4: timing map. Audio is the master clock.
In:  timing/lines.json (exact line offsets from the stitch), timing/words.json (Whisper word timestamps of vo.wav), plan.json
Out: video/src/data/timeline.json  {fps, total, vo_s, lines{id:{s,e}}, words[{text,startMs,endMs}], emph{id:{word:frame}}}
Caption text is the SCRIPT's words (exact spelling), timed by aligning them to Whisper's words.
Checks: every line has nonzero duration; caption pages <= 2 lines of <= 42 chars (checked in Remotion by layout width)."""
import json
import sys
from pathlib import Path

import numpy as np

from process_voice import norm

FPS = 30
OUTRO_TAIL_S = 1.5
ROOT = Path(__file__).parent
plan = json.loads((ROOT / 'plan.json').read_text())
lines = {l['id']: l for l in json.loads((ROOT / 'timing/lines.json').read_text())}
heard = json.loads((ROOT / 'timing/words.json').read_text())

# script words with their normalized tokens
sw = []  # (line_id, display_word, [tokens])
for l in plan['script']:
    for w in l['text'].split():
        sw.append((l['id'], w, norm(w)))
ref, owner = [], []
for i, (_, _, toks) in enumerate(sw):
    ref += toks
    owner += [i] * len(toks)
H, Ht = [], []
for k, h in enumerate(heard):
    for t in norm(h['word']):
        H.append(t)
        Ht.append((h['start'], h['end']))
n, m = len(ref), len(H)
d = np.zeros((n + 1, m + 1), int)
d[:, 0], d[0, :] = range(n + 1), range(m + 1)
for i in range(1, n + 1):
    for j in range(1, m + 1):
        d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (ref[i - 1] != H[j - 1]))
i, j, match = n, m, {}
while i > 0 and j > 0:
    if d[i, j] == d[i - 1, j - 1] + (ref[i - 1] != H[j - 1]):
        match[i - 1] = j - 1
        i, j = i - 1, j - 1
    elif d[i, j] == d[i - 1, j] + 1:
        i -= 1
    else:
        j -= 1
times: list = [None] * len(sw)
for ti, wi in enumerate(owner):
    if ti in match:
        s, e = Ht[match[ti]]
        times[wi] = (min(s, times[wi][0]), max(e, times[wi][1])) if times[wi] else (s, e)
# unmatched script words: spread inside their line's exact span between matched neighbours
for wi, (lid, _, _) in enumerate(sw):
    if times[wi] is None:
        prev = next((times[k][1] for k in range(wi - 1, -1, -1) if times[k] and sw[k][0] == lid), lines[lid]['start_s'])
        nxt = next((times[k][0] for k in range(wi + 1, len(sw)) if times[k] and sw[k][0] == lid), lines[lid]['end_s'])
        times[wi] = (prev, max(prev + 0.05, nxt))
# clamp each word into its line span (the stitch offsets are exact)
words = []
for (lid, w, _), (s, e) in zip(sw, times):
    s = min(max(s, lines[lid]['start_s']), lines[lid]['end_s'])
    e = min(max(e, s + 0.05), lines[lid]['end_s'] + 0.2)
    words.append({'text': w, 'line': lid, 'startMs': round(s * 1000), 'endMs': round(e * 1000)})

emph = {}
for l in plan['script']:
    ws = [w for w in words if w['line'] == l['id']]
    emph[l['id']] = {}
    for phrase in l['emphasis']:
        first = norm(phrase)[0] if norm(phrase) else ''
        hit = next((w for w in ws if norm(w['text'])[:1] == [first]), None)
        if hit:
            emph[l['id']][phrase] = round(hit['startMs'] / 1000 * FPS)
vo_s = max(l['end_s'] for l in lines.values())
out = {'fps': FPS, 'vo_s': vo_s, 'total': int(np.ceil((vo_s + OUTRO_TAIL_S) * FPS)),
       'lines': {k: {'s': round(v['start_s'] * FPS), 'e': round(v['end_s'] * FPS)} for k, v in lines.items()},
       'words': words, 'emph': emph}
bad = [k for k, v in out['lines'].items() if v['e'] <= v['s']]
missing = [l['id'] for l in plan['script'] if l['id'] not in lines]
if bad or missing:
    sys.exit(f'timeline check failed: zero-length {bad}, missing {missing}')
dst = ROOT / 'video/src/data/timeline.json'
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(out, indent=1, ensure_ascii=False))
matched = sum(t in match for t in range(len(ref)))
print(f"lines {len(lines)}, words {len(words)} ({matched}/{len(ref)} tokens matched to Whisper), "
      f"vo {vo_s:.2f} s, total {out['total']} frames ({out['total'] / FPS:.1f} s)")
