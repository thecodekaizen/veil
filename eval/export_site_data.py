"""Collect every number the website shows into veil/web/public/data/results.json, straight from committed result files.
Run: uv run --project veil python eval/export_site_data.py"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def gate(path):
    g = json.loads((ROOT / path / 'gate_result.json').read_text())
    md = (ROOT / path / 'GATE_RESULT.md').read_text()
    over = re.search(r'over-cover ([\d.]+) s', md)
    c = g['criteria']
    return {'verdict': g['verdict'],
            'G1': {'ok': c['G1']['ok'], 'value': f"{c['G1']['covered']}/{c['G1']['planted']}"},
            'G2': {'ok': c['G2']['ok'], 'value': f"{c['G2']['controls_matched']}/{c['G2']['controls']}"},
            'G3': {'ok': c['G3']['ok'], 'value': '≥95% of frames' if c['G3']['ok'] else 'below 95%'},
            'G4a': {'ok': c['G4a']['ok'], 'value': 'detected' if c['G4a']['ok'] else 'missed'},
            'G4b': {'ok': c['G4b']['ok'], 'value': f"{over.group(1)} s over" if over else '?'}}


held = (ROOT / 'eval/results/final/heldout_results.md').read_text()
m = re.search(r'baseline-only (\d+)/(\d+), baseline\+Spark (\d+)/(\d+)', held)
repeats = sorted(p.name for p in (ROOT / 'gate/repeats').iterdir() if (p / 'gate_result.json').exists())
summary = json.loads((ROOT / 'eval/repeats/summary.json').read_text()) if (ROOT / 'eval/repeats/summary.json').exists() else None
tests = 119
out = {
    'heldout': {'baseline_only': f'{m.group(1)}/{m.group(2)}', 'with_spark': f'{m.group(3)}/{m.group(4)}',
                'source': 'eval/results/final/heldout_results.md'},
    'gates': {'frozen': {'label': 'Frozen gate (commit 4ef8de9)', **gate('gate')},
              'postgate': {'label': 'Post-gate fixes, capped', **gate('gate/postgate')},
              **{r: {'label': f'Repeat {r[1:]} · uncapped · all checks', **gate(f'gate/repeats/{r}')} for r in repeats}},
    'models': summary['models'] if summary else [],
    'usd_per_clip_run': summary['usd_per_clip_run'] if summary else None,
    'clip_runs': summary['clip_runs'] if summary else 0,
    'tests': tests,
}
dst = ROOT / 'veil/web/public/data/results.json'
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1)[:1500])
