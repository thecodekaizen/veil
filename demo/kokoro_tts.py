"""Narration with Kokoro-82M (Apache-2.0): a natural studio voice, NOT the author's voice (owner's choice, 2026-11-01).
Run: .venv-kokoro/bin/python kokoro_tts.py --voice af_heart [--only id,id] [--out voice/kokoro] [--speed 1.0]
Writes one WAV per script line; process_voice.py then checks and stitches them as usual."""
import argparse, json, re
from pathlib import Path
import numpy as np
import soundfile as sf
from kokoro import KPipeline

SAY = [(r'\bSAM 3\.1\b', 'Sam three point one'), (r'\bOCR\b', 'O C R'), (r'\bVeil\b', '[Veil](/veɪl/)'),
       (r'\bKulkarni\b', '[Kulkarni](/kʊlˈkɑːɹni/)'), (r'—', ', '), (r'\bre-reads\b', 'rereads'), (r'\bre-runs\b', 'reruns'),
       (r'\bre-ran\b', 'reran'), (r'\bpost-gate\b', 'post gate'), (r'\bheld-out\b', 'held out'), (r'\bMuse\b', '[Muse](/mjuːz/)')]


def speakable(text):
    for a, b in SAY:
        text = re.sub(a, b, text)
    return text


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('--voice', default='af_heart'); ap.add_argument('--only', default=''); ap.add_argument('--out', default='voice/kokoro')
    ap.add_argument('--speed', type=float, default=0.92)
    a = ap.parse_args()
    pipe = KPipeline(lang_code='a')
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, a.only.split(',')))
    for line in json.loads(Path('plan.json').read_text())['script']:
        if only and line['id'] not in only:
            continue
        audio = np.concatenate([r.audio.numpy() for r in pipe(speakable(line['text']), voice=a.voice, speed=a.speed)])
        sf.write(out / f"line_{line['id']}_{a.voice}.wav", audio, 24000)
        print(line['id'], 'done', flush=True)
