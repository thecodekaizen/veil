# Demo setup log (2026-11-01)
- Python 3.11 venv: `uv venv --python 3.11 demo/.venv`
- `mlx-whisper==0.4.2` (word timestamps, Apple Silicon) into demo/.venv
- `playwright@1.64.1` (exact) in demo/capture (matches cached chromium-1248)
- Not yet installed: Remotion (phase 6), Chatterbox (only if clone/hybrid)
- Whisper model `mlx-community/whisper-large-v3-turbo` (downloaded by mlx-whisper on first run, HF cache)
- Phase 3 pipeline tested 2026-11-01 on throwaway macOS `say` takes (scratchpad, deleted): -16.01 LUFS, -1.5 dBTP; checks flagged synthetic-voice WER as intended
- .venv-tts: chatterbox-tts==0.1.7 (+ setuptools==75.8.0 for resemble-perth's pkg_resources import); model ResembleAI/chatterbox-turbo
- Remotion 4.0.539 (create-video blank) + @remotion/{captions,media-utils,transitions,google-fonts,media}@4.0.539 in demo/video
