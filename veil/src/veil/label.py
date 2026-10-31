"""Labelling helper: extract 4 fps frames and write a self-contained labeler.html."""
import hashlib
import json
import subprocess
from pathlib import Path

LABEL_FPS = 4


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def probe(clip: Path) -> dict:
    out = subprocess.check_output(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
         'stream=width,height,r_frame_rate:format=duration', '-of', 'json', str(clip)])
    info = json.loads(out)
    num, den = info['streams'][0]['r_frame_rate'].split('/')
    return {'width': info['streams'][0]['width'], 'height': info['streams'][0]['height'],
            'fps': float(num) / float(den), 'duration': float(info['format']['duration'])}


def prepare(clip: Path, out_root: Path) -> Path:
    """Extract frames at LABEL_FPS (native resolution) and write labeler.html; returns its path."""
    clip_id = clip.stem
    folder = out_root / clip_id
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob('frame_*.jpg'):
        old.unlink()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(clip), '-vf', f'fps={LABEL_FPS}',
                    '-q:v', '3', str(folder / 'frame_%04d.jpg')], check=True)
    frames = sorted(p.name for p in folder.glob('frame_*.jpg'))
    meta = probe(clip)
    sha = sha256_file(clip)
    config = {'clip_id': clip_id, 'clip_sha256': sha, 'fps': round(meta['fps'], 3), 'label_fps': LABEL_FPS,
              'frames': frames}
    html = (Path(__file__).with_name('label_template.html').read_text()
            .replace('__CONFIG__', json.dumps(config))
            .replace('__CLIP_ID__', clip_id).replace('__WIDTH__', str(meta['width']))
            .replace('__HEIGHT__', str(meta['height'])).replace('__FPS__', f"{meta['fps']:.2f}")
            .replace('__DURATION__', f"{meta['duration']:.1f}"))
    target = folder / 'labeler.html'
    target.write_text(html)
    return target
