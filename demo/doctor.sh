#!/usr/bin/env bash
# Demo pipeline dependency check. Prints OK / MISSING per item; exits 1 if a required item is missing.
cd "$(dirname "$0")"
fail=0
row(){ printf '%-34s %s\n' "$1" "$2"; }
chk(){ if eval "$2" >/dev/null 2>&1; then row "$1" "OK"; else row "$1" "MISSING ($3)"; [ "$3" = required ] && fail=1; fi; }
row "platform" "$(uname -m), $(sysctl -n hw.memsize | awk '{print $1/1073741824" GB"}'), $(sysctl -n machdep.cpu.brand_string)"
chk "node >= 22" '[ "$(node -v | sed "s/v//;s/\..*//")" -ge 22 ]' required
chk "ffmpeg libx264" 'ffmpeg -hide_banner -encoders | grep -q libx264' required
chk "ffmpeg aac" 'ffmpeg -hide_banner -encoders | grep -q " aac "' required
chk "ffmpeg loudnorm/afftdn" 'ffmpeg -hide_banner -filters | grep -q loudnorm && ffmpeg -hide_banner -filters | grep -q afftdn' required
chk "python 3.11 venv (demo/.venv)" '.venv/bin/python -c "import sys;assert sys.version_info[:2]==(3,11)"' required
chk "mlx-whisper (word timestamps)" '.venv/bin/python -c "import mlx_whisper"' required
chk "Playwright Chromium" 'ls ~/Library/Caches/ms-playwright | grep -q chromium' required
chk "Remotion project (demo/video)" '[ -f video/package.json ]' "phase 6"
chk "TTS (chatterbox)" '.venv/bin/python -c "import chatterbox"' "only if voice_mode=clone/hybrid"
chk "voice reference" '[ -f voice/reference.wav ]' "only if voice_mode=clone/hybrid"
chk "music (demo/audio/music.*)" 'ls audio/music.* ' "phase 7, user-provided"
chk "brand logo" '[ -f ../brand/logo.svg ] || [ -f brand/logo.svg ]' "optional"
exit $fail
