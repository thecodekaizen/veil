"""Test natural replacement (demo replacement) and face blur on the real camera challenge video."""
import json
import time
from pathlib import Path
from veil import VeilClient
from veil.providers.common import save

def main():
    root = Path('artifacts/public-footage-001')
    source = root / 'challenge.mp4'
    evidence = root / 'normal-run/provider-evidence'
    timeline = json.loads((evidence / 'timeline.json').read_text())

    # Set face to BLUR instead of black box cover
    for track in timeline['visual_tracks']:
        if track['category'] == 'face':
            track['action'] = 'blur'
            print(f"[*] Set track {track['id']} ({track['category']}) action to 'blur'")

    # Set corners precisely matching frame 12 box [68, 158, 268, 188]
    surfaces = [{
        'track_id': 'phone-observed-0',
        'kind': 'screen',
        'start_frame': 12,
        'corners': [
            [70.0, 160.0],
            [266.0, 160.0],
            [266.0, 186.0],
            [70.0, 186.0],
        ],
        'original_identifiers': ['202-555-0189'],
    }]

    output_dir = root / 'natural_replacement_demo'
    output_dir.mkdir(parents=True, exist_ok=True)
    out_video = output_dir / 'natural_real_camera.mp4'

    print(f"[*] Running protect_natural on {source.name} via http://127.0.0.1:8020 ...")
    start = time.monotonic()
    with VeilClient('http://127.0.0.1:8020') as client:
        result = client.protect_natural(
            source,
            out_video,
            surfaces,
            media_is_synthetic_or_consented=True,
            timeline=timeline,
        )

    elapsed = time.monotonic() - start
    save(output_dir / 'natural_real_result.json', result)
    print(f"[+] Completed in {elapsed:.2f}s!")
    print(f"    Job ID: {result['job']['id']}")
    print(f"    Status: {result['job']['status']}")
    print(f"    Downloaded: {result['downloaded']}")
    print(f"    Natural Status: {result['natural_review']['status']}")
    decisions = result['natural_review'].get('track_decisions', [])
    for d in decisions:
        print(f"    Track {d['track_id']}: proposed={d['proposed_strategy']}, final={d['final_strategy']}, natural_frames={d['natural_frames']}, fallback_frames={len(d['opaque_fallback_frames'])}")
    if out_video.exists():
        print(f"    Output MP4: {out_video} ({out_video.stat().st_size} bytes)")

if __name__ == '__main__':
    main()
