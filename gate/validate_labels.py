"""Validate a gate label file: uv run --project veil python -m gate.validate_labels gate/labels/c1.json"""
import hashlib
import sys
from pathlib import Path

from pydantic import ValidationError

from gate.labels_schema import Labels


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print('usage: python -m gate.validate_labels FILE')
        return 2
    path = Path(argv[0])
    try:
        labels = Labels.model_validate_json(path.read_text())
    except (ValidationError, OSError) as exc:
        print(f'INVALID {path}:\n{exc}')
        return 1
    clip = Path('gate/clips') / f'{labels.clip_id}.mp4'
    if clip.exists():
        actual = hashlib.sha256(clip.read_bytes()).hexdigest()
        if actual != labels.clip_sha256:
            print(f'INVALID {path}: clip_sha256 does not match {clip} ({actual})')
            return 1
        sha_note = f'sha256 matches {clip}'
    else:
        sha_note = f'{clip} not found; sha256 not checked'
    visual = sum(leak.kind == 'visual' for leak in labels.leaks)
    print(f'OK {path}: {visual} visual leaks, {len(labels.leaks) - visual} audio leaks, '
          f'{len(labels.safe_controls)} safe controls; {sha_note}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
