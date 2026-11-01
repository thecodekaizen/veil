"""Clone the creator's OWN voice (consented: they asked) with Chatterbox and generate script lines.
Reference: voice/reference.wav (built from their own recorded lines h1, h3, p1, a3).
Per line: 3 takes, Whisper-checked; best take -> voice/raw/line_<id>.wav (their own recordings move to voice/takes/user/).
Run: .venv-tts/bin/python tts.py [--model turbo|standard] [--only id,id] [--takes 3]"""
import argparse, json, re, shutil, subprocess
from pathlib import Path
import torch, torchaudio

SAY = [(r'\bSAM 3\.1\b', 'Sam three point one'), (r'\bOCR\b', 'O C R'),
       (r'—', ', '), (r'\bre-reads\b', 'rereads'), (r'\bpost-gate\b', 'post gate'), (r'\bheld-out\b', 'held out')]


# Lines whose short fragments the model garbles: same words, joined into phrases (pronunciation only).
PHRASED = {'c1': 'Models propose, and code decides. Veil, built solo, with Muse Spark, Sam three point one, and Muse Voice.'}


def speakable(text, line_id=''):
    if line_id in PHRASED:
        return PHRASED[line_id]
    for a, b in SAY:
        text = re.sub(a, b, text)
    return text


ap = argparse.ArgumentParser()
ap.add_argument('--model', default='turbo'); ap.add_argument('--only', default=''); ap.add_argument('--takes', type=int, default=5)
ap.add_argument('--out', default='voice/tts'); ap.add_argument('--round', type=int, default=0)
a = ap.parse_args()
dev = 'mps' if torch.backends.mps.is_available() else 'cpu'
if a.model == 'turbo':
    from chatterbox.tts_turbo import ChatterboxTurboTTS as M
    settings = [dict(temperature=t) for t in (0.5, 0.6, 0.7, 0.8, 0.9)]
else:
    from chatterbox.tts import ChatterboxTTS as M
    settings = [dict(exaggeration=e, cfg_weight=c) for e, c in ((0.45, 0.5), (0.55, 0.4), (0.65, 0.3))]
model = M.from_pretrained(device=dev)
plan = json.loads(Path('plan.json').read_text())
only = set(filter(None, a.only.split(',')))
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
for line in plan['script']:
    if only and line['id'] not in only:
        continue
    for k, s in enumerate(settings[:a.takes]):
        torch.manual_seed(1000 + k + 100 * a.round)
        wav = model.generate(speakable(line['text'], line['id']), audio_prompt_path='voice/reference.wav', **s)
        torchaudio.save(str(out / f"line_{line['id']}_{a.model}_t{k + 5 * a.round}.wav"), wav.cpu(), model.sr)
    print(line['id'], 'done', flush=True)
