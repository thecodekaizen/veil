#!/usr/bin/env bash
# Phase 7/8: final audio mix + loudness versions. Video stream is copied untouched.
# If demo/audio/music.* exists it is looped/cut to length and sidechain-ducked under the VO
# (about -20 dB under speech, 200 ms attack/release); otherwise VO only.
# Out: out/veil-demo-web.mp4 (-16 LUFS), out/veil-demo-social.mp4 (-14 LUFS), true peak <= -1 dBTP.
set -euo pipefail
cd "$(dirname "$0")"
IN=${1:-out/veil-draft.mp4}
M=$(ls audio/music.* 2>/dev/null | head -1 || true)
if [ -n "$M" ]; then
  FC="[1:a]aloop=loop=-1:size=2e9,volume=-12dB[m];[0:a]asplit=2[vo][key];[m][key]sidechaincompress=threshold=0.03:ratio=8:attack=200:release=250[duck];[vo][duck]amix=inputs=2:duration=first:normalize=0[a]"
  INPUTS=(-i "$IN" -i "$M")
  echo "music: $M (ducked)"
else
  FC="[0:a]anull[a]"
  INPUTS=(-i "$IN")
  echo "music: none (VO only)"
fi
for target in web:-16 social:-14; do
  name=${target%%:*}; lufs=${target##*:}
  ffmpeg -v error -y "${INPUTS[@]}" -filter_complex "$FC;[a]loudnorm=I=$lufs:TP=-1.5:LRA=11[out]" \
    -map 0:v -map "[out]" -c:v copy -c:a aac -b:a 320k -ar 48000 -movflags +faststart "out/veil-demo-$name.mp4"
  ffmpeg -hide_banner -i "out/veil-demo-$name.mp4" -af loudnorm=print_format=summary -vn -f null - 2>&1 | grep -E "Input Integrated|Input True Peak" | sed "s/^/$name: /"
done
