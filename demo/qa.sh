#!/usr/bin/env bash
# Phase 8 QA on a rendered MP4: duration, black frames, silent gaps, loudness, WER vs script, frames every 10 s.
set -euo pipefail
cd "$(dirname "$0")"
F=${1:-out/veil-draft.mp4}
echo "file: $F"
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,sample_rate -of compact "$F"
echo "-- black frames (>=0.5 s):"; ffmpeg -hide_banner -i "$F" -vf blackdetect=d=0.5:pix_th=0.05 -an -f null - 2>&1 | grep -o "black_start.*" || echo none
echo "-- silences > 1.2 s:"; ffmpeg -hide_banner -i "$F" -af silencedetect=n=-45dB:d=1.2 -vn -f null - 2>&1 | grep -o "silence_duration.*" || echo none
echo "-- loudness:"; ffmpeg -hide_banner -i "$F" -af loudnorm=print_format=summary -vn -f null - 2>&1 | grep -E "Input Integrated|Input True Peak"
echo "-- WER of final audio vs script:"
ffmpeg -v error -y -i "$F" -vn -ac 1 -ar 16000 /tmp/qa_audio.wav
.venv/bin/python - <<'P' 2>&1 | grep -v "Fetching\|it/s"
import json
from process_voice import transcribe, norm, wer
from pathlib import Path
plan = json.loads(Path('plan.json').read_text())
ref = norm(' '.join(l['text'] for l in plan['script']))
e, miss = wer(ref, norm(transcribe(Path('/tmp/qa_audio.wav'))['text']))
print(f'WER {e:.1%}; words missing: {miss}')
P
mkdir -p review/final; rm -f review/final/f_*.png
ffmpeg -v error -i "$F" -vf "fps=1/10,scale=640:-1" review/final/f_%02d.png
ffmpeg -v error -y -pattern_type glob -i 'review/final/f_*.png' -vf "tile=4x4:padding=6:color=0x333333" -frames:v 1 review/final_contact.png
echo "contact: review/final_contact.png"
