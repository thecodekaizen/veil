"""Standard-tool contrast for the demo: redact a run using ONLY its fixed baseline-class tracks (face, plate, phone screen, document).
Same input, same redact code; writes RUN_fixed/output.mp4. Usage: uv run --project veil python demo/make_fixed_class_export.py runs/c2demo"""
import json, shutil, sys
from pathlib import Path

from veil.stages import redact

src = Path(sys.argv[1]); dst = src.with_name(src.name + '_fixed'); dst.mkdir(exist_ok=True)
for f in ('input.mp4', 'discover.json', 'listen.json', 'audio.wav'):
    if (src / f).exists():
        shutil.copyfile(src / f, dst / f)
t = json.loads((src / 'track_final.json').read_text())
t['masklets'] = [m for m in t['masklets'] if m['concept_id'].startswith('baseline-')]
(dst / 'track_final.json').write_text(json.dumps(t))
art = redact.run(dst)
print(dst / art.output_path, [m['track_id'] for m in t['masklets']])
