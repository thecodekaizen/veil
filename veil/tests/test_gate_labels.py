import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gate.labels_schema import Labels  # noqa: E402

SHA = 'a' * 64


def box(t=1.0):
    return {'t_s': t, 'x': 10, 'y': 10, 'w': 50, 'h': 30}


def labels(**over):
    base = {'clip_id': 'c1', 'clip_sha256': SHA, 'fps': 30, 'leaks': [
        {'leak_id': 'L1', 'kind': 'visual', 'concept': 'delivery label', 'in_baseline': False,
         'visible_ranges': [[1, 5]], 'ref_boxes': [box(1), box(4)]},
        {'leak_id': 'A1', 'kind': 'audio', 'concept': 'spoken number', 'in_baseline': True,
         'audio': {'text': 'nau aath', 'digits': '9876543210', 't_start': 2, 't_end': 6}}],
        'safe_controls': [{'control_id': 'C1', 'description': 'code editor', 'visible_ranges': [[0, 8]],
                           'ref_boxes': [box(2)]}]}
    base.update(over)
    return base


def test_round_trip():
    parsed = Labels.model_validate(labels())
    assert Labels.model_validate_json(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize('mutate', [
    lambda d: d['leaks'][0].update(ref_boxes=[box()]),                     # needs 2-3 boxes
    lambda d: d['leaks'][0].update(visible_ranges=[]),                     # visual needs ranges
    lambda d: d['leaks'][0].update(visible_ranges=[[5, 1]]),               # reversed range
    lambda d: d['leaks'][1]['audio'].update(digits='12345'),               # not 10 digits
    lambda d: d['leaks'][1]['audio'].update(t_end=1),                      # end before start
    lambda d: d['leaks'][1].update(ref_boxes=[box(), box()]),              # audio with boxes
    lambda d: d.update(clip_sha256='xyz'),                                 # bad sha
    lambda d: d['leaks'][1].update(leak_id='L1'),                          # duplicate id
    lambda d: d['leaks'][0].update(extra_field=1),                         # extra keys forbidden
])
def test_rejects_invalid(mutate):
    data = labels()
    mutate(data)
    with pytest.raises(ValidationError):
        Labels.model_validate(json.loads(json.dumps(data)))
