"""Convert capture/out2/flow_<name>.webm + events_<name>.json into video/public/flows2/flow_<name>.mp4 and video/src/data/flows2.json
(duration_s, events with t in seconds), the format Main.tsx's FlowScene reads. Run from demo/: python3 capture/flows2_to_remotion.py"""
import json, subprocess
from pathlib import Path

SRC, DST, DATA = Path('capture/out2'), Path('video/public/flows2'), Path('video/src/data/flows2.json')
DST.mkdir(parents=True, exist_ok=True)
out = {}
for ev in sorted(SRC.glob('events_*.json')):
    name = ev.stem[len('events_'):]
    webm, mp4 = SRC / f'flow_{name}.webm', DST / f'flow_{name}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', webm, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-pix_fmt', 'yuv420p', '-an', mp4], check=True)
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4], capture_output=True, text=True).stdout)
    e = json.loads(ev.read_text())
    out[name] = {'duration_s': round(dur, 2), 'events': [{'t': round(x['t_ms'] / 1000, 2), 'type': x['type'], 'box': x['box']} for x in e['events']]}
    print(name, out[name]['duration_s'])
DATA.write_text(json.dumps(out, indent=1))
