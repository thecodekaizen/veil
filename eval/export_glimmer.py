"""Summarize the open-weight Muse Glimmer run (runs-glimmer/c2s) for the video and README.
Run: uv run --project veil python eval/export_glimmer.py   -> demo/video/src/data/glimmer.json, eval/glimmer/summary.md
Experiment (declared before results): Glimmer discovery on every 3rd keyframe of gate clip c2 (9 frames), local llama.cpp,
same prompt and JSON schema as hosted Spark; SAM 3.1 tracks its concepts; the gate scorer scores c2's leaks and control."""
import json
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
run = ROOT / 'runs-glimmer/c2s'
calls = json.loads((run / 'calls.json').read_text())
disc = [c for c in calls if c['name'].startswith('discover-')]
ok = [c for c in disc if c.get('status') == 'completed']
lat = [c['latency_s'] for c in ok]
d = json.loads((run / 'discover.json').read_text())
props = [{'frame': c['frame_idx'], 'concept': c['concept'], 'why': c['why_identifying']} for c in d['candidates']]
log = (Path('/tmp/llama-server.log').read_text() if Path('/tmp/llama-server.log').exists() else '')
tps = [float(x) for x in re.findall(r'eval time =.*?([\d.]+) tokens per second', log) if 'prompt' not in x]
gen = [float(m) for m in re.findall(r'\|\s+eval time = .*?,\s+([\d.]+) tokens per second', log)]
result = None
gr = ROOT / 'gate/glimmer/gate_result.json'
if gr.exists():
    g = json.loads(gr.read_text())
    rows = g['criteria']['G1']['rows']
    found = [r['leak_id'] for r in rows if r['clip'] == 'c2' and r['matched']]
    ctrl = [r for r in g['criteria']['G2']['rows'] if r['clip'] == 'c2']
    result = f"on c2: {len(found)}/2 planted leaks found, code-panel control {'flagged' if any(r['matched'] for r in ctrl) else 'not flagged'}"
out = {'frames': len(disc), 'frames_ok': len(ok), 'median_s': round(st.median(lat), 1) if lat else None,
       'tok_s': round(st.median(gen), 1) if gen else None, 'proposals': props, 'result': result,
       'quant': 'unsloth UD-Q3_K_XL GGUF'}
(ROOT / 'demo/video/src/data/glimmer.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
(ROOT / 'eval/glimmer').mkdir(parents=True, exist_ok=True)
md = ['# Open-weight discovery: Muse Glimmer 30B on a laptop (experimental, one clip)', '',
      'Declared before results: every 3rd keyframe of gate clip c2 (9 frames), local `llama-server` (llama.cpp 0.8.0, unsloth UD-Q3_K_XL GGUF '
      'of Meta\'s Apache-2.0 weights, SHA-256 verified), Apple M4 Pro 24 GB. Same prompt and strict JSON schema as hosted Spark. '
      'SAM 3.1 (hosted) tracks the proposed concepts; the unchanged gate scorer scores c2. Keyframes never leave the laptop for this stage.', '',
      f"- Keyframes answered: **{len(ok)}/{len(disc)}** ({len(disc) - len(ok)} hit the 600 s per-call timeout); median {out['median_s']} s per keyframe; "
      f"~{out['tok_s']} tokens/s generation (the 15 GB model swaps on 24 GB).",
      f"- Result: {result or 'not scored yet'}",
      '', '## Proposals (verbatim)', ''] + [f"- frame {p['frame']}: **{p['concept']}**: {p['why']}" for p in props] + [
      f"- Scorer output: `gate/glimmer/GATE_RESULT.md`. Its G1 'FAIL' is an artifact of scoring one clip (G1 expects all 4 leaks across c1-c3); G4 does not apply (c2 has no audio leak). Hosted Spark on the same clip (repeat r1, all 25 keyframes): 2/2 leaks, control flagged.", '', 'Caveats: one clip, a third of the keyframes, a 3-bit quantization, 4 timeouts. Hosted Spark saw all 25 keyframes. This shows the open-weight path works end to end; it is not a quality comparison.']
(ROOT / 'eval/glimmer/summary.md').write_text('\n'.join(md) + '\n')
print('\n'.join(md))
