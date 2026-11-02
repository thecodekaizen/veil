"""Demo-only variant of gate clip c2 WITHOUT the safe-control code panel (the gate clips and labels are untouched).
Same licensed footage, same planted fictional leaks (notification L2, door nameplate L3), same positions and timings.
Usage: uv run --project veil python demo/make_c2_demo.py  -> gate/clips/c2demo.mp4 (gitignored)"""
import shutil
from pathlib import Path

from gate import make_composite_clips as mc

if __name__ == '__main__':
    spec = dict(mc.CLIPS['c2'], controls=[])
    mc.OUT_CLIPS.mkdir(parents=True, exist_ok=True)
    tmp = Path('gate/clips/_tmp_demo'); tmp.mkdir(parents=True, exist_ok=True)
    out, layers, _ = mc.build('c2demo', spec, tmp)
    shutil.rmtree(tmp)
    print(out, [pid for pid, *_ in layers])
