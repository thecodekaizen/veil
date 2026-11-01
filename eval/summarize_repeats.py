"""Summarize the end-to-end repeat runs (runs-rep/r*/c*): gate criteria per repeat and per-model call ledgers.
Run: uv run --project veil python eval/summarize_repeats.py   ->  eval/repeats/summary.md, summary.json
Each repeat re-runs every stage (fresh Spark discovery, SAM tracking, Voice), cap 50 concepts, up to 2 logged SAM retries."""
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
GATE_DIR, RUN_DIR, OUT_DIR = (sys.argv[1:4] if len(sys.argv) > 3 else ('gate/repeats', 'runs-rep', 'eval/repeats'))
reps = sorted(p.name for p in (ROOT / GATE_DIR).iterdir() if (p / 'gate_result.json').exists())
gates = {r: json.loads((ROOT / f'{GATE_DIR}/{r}/gate_result.json').read_text()) for r in reps}
calls = defaultdict(list)
clips_cost = []
not_checked = defaultdict(int)
for r in reps:
    for clip in sorted((ROOT / f'{RUN_DIR}/{r}').glob('c*')):
        if not clip.is_dir():
            continue
        cost = 0.0
        for led in clip.glob('calls*.json'):
            for c in json.loads(led.read_text()):
                m = c.get('model', '?')
                key = 'muse-voice-transcribe-1.0' if 'voice' in m else ('sam-3.1' if 'sam' in m else m)
                calls[key].append(c)
                cost += c.get('estimated_usd') or 0
        clips_cost.append(cost)
        audit = json.loads((clip / 'audit.json').read_text())
        not_checked[r] += sum(f['status'] == 'NOT_CHECKED' for f in audit['findings'])



def over_cover(r):
    txt = (ROOT / f'{GATE_DIR}/{r}/GATE_RESULT.md').read_text()
    line = next((l for l in txt.splitlines() if l.startswith('| G4b')), '')
    return line.split('over-cover')[1].split(',')[0].strip() if 'over-cover' in line else '?'


rows = []
for r, g in gates.items():
    c = g['criteria']
    pf = lambda k: 'PASS' if c[k]['ok'] else 'FAIL'
    rows.append({'repeat': r,
                 'G1 discovery': f"{pf('G1')} {c['G1']['covered']}/{c['G1']['planted']}",
                 'G2 false flags': f"{pf('G2')} {c['G2']['controls_matched']}/{c['G2']['controls']}",
                 'G3 tracking': pf('G3'), 'G4a digits': pf('G4a'),
                 'G4b mute window': f"{pf('G4b')} {over_cover(r)} over",
                 'G5 output re-check': 'UNRESOLVED listed' if not c['G5']['ok'] else 'PASS',
                 'NOT_CHECKED findings': not_checked[r], 'verdict': g['verdict']})
model_rows = []
for m, cs in sorted(calls.items()):
    lat = [c['latency_s'] for c in cs if c.get('latency_s') is not None]
    model_rows.append({'model': m, 'calls': len(cs), 'failed': sum(c.get('status') != 'completed' for c in cs),
                       'median_latency_s': round(st.median(lat), 2) if lat else None,
                       'p90_latency_s': round(sorted(lat)[int(0.9 * (len(lat) - 1))], 2) if lat else None,
                       'est_usd': round(sum(c.get('estimated_usd') or 0 for c in cs), 2)})
out = {'repeats': rows, 'models': model_rows, 'clip_runs': len(clips_cost),
       'usd_per_clip_run': {'mean': round(st.mean(clips_cost), 2), 'min': round(min(clips_cost), 2), 'max': round(max(clips_cost), 2)},
       'total_usd': round(sum(clips_cost), 2)}
(ROOT / OUT_DIR).mkdir(parents=True, exist_ok=True)
(ROOT / OUT_DIR / 'summary.json').write_text(json.dumps(out, indent=1))
keys = [k for k in rows[0] if k != 'repeat'] if rows else []
md = ['# End-to-end repeats (post-gate, NOT the frozen gate)', '',
      'Each repeat re-ran every stage on c1-c3 (fresh Spark discovery, SAM 3.1 tracking with up to 2 logged retries, Voice), '
      'concept cap 50, verify stage on, frozen bleep method. Same clips as the gate, so this measures run-to-run variance, not generalization.', '',
      '| ' + ' | '.join(['repeat'] + keys) + ' |', '|' + '---|' * (len(keys) + 1)]
md += ['| ' + ' | '.join([r['repeat']] + [str(r[k]) for k in keys]) + ' |' for r in rows]
md += ['', '## Model calls (all repeats)', '', '| model | calls | failed | median latency s | p90 latency s | est. USD |', '|---|---|---|---|---|---|']
md += [f"| {m['model']} | {m['calls']} | {m['failed']} | {m['median_latency_s']} | {m['p90_latency_s']} | {m['est_usd']} |" for m in model_rows]
md += ['', f"Clip runs: {out['clip_runs']}; est. USD per clip run: mean {out['usd_per_clip_run']['mean']} "
       f"(min {out['usd_per_clip_run']['min']}, max {out['usd_per_clip_run']['max']}); total {out['total_usd']}. "
       'Estimates from the call ledgers, not reconciled to billing.']
(ROOT / OUT_DIR / 'summary.md').write_text('\n'.join(md) + '\n')
print('\n'.join(md))
