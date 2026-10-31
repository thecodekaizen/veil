import json
from pathlib import Path

import pytest

from veil.media.keyframes import select_times
from veil.schemas import Candidate, Concept, DiscoverArtifact, Word
from veil.stages import discover, listen, track
from veil.validators.pii import bleep_intervals, phone_hits
from veil.validators.spoken_digits import digit_runs

ART = Path(__file__).resolve().parents[1] / 'artifacts' / 'voice-timing-001'


def words(text, t0=0.0, step=0.3):
    return [Word(text=w, t_start=t0 + i * step, t_end=t0 + i * step + 0.25) for i, w in enumerate(text.split())]


def digits(text, **k):
    return [r.digits for r in digit_runs(words(text, **k))]


@pytest.mark.parametrize('text,expected', [
    ('mera number hai nau aath saat chhe paanch, char teen do ek zero', ['9876543210']),
    ('98765 43210', ['9876543210']),
    ('number is double nine eight seven six five four', ['9987654']),
    ('two zero two five five five zero one four six', ['2025550146']),
    ('९८७६५ ४३२१०', ['9876543210']),
    ('नौ आठ सात छह पांच चार तीन दो एक शून्य', ['9876543210']),
    ('nau aath saat saha paach char teen don ek shunya', ['9876543210']),
    ('nine eight uh seven six matlab five four three', ['9876543']),
    ('triple five one two three four', ['5551234']),
    ('+91 98765 43210', ['919876543210']),
])
def test_positive_runs(text, expected):
    assert digits(text) == expected


@pytest.mark.parametrize('text', [
    'do minute ruko', 'ek baar aur', 'teen log aaye the', 'saat baje milte hain', 'in 2026 we went',
    'do teen log', 'nine eight seven', 'meri umar do saal hai teen bachche',
    'one two three four five',  # 5 digits: below the 6-digit minimum
])
def test_negatives_do_not_fire(text):
    assert digits(text) == []


def test_gap_over_1_5s_breaks_run():
    ws = words('nine eight seven') + words('six five four', t0=5.0)
    assert digit_runs(ws) == []


def test_non_filler_word_breaks_run():
    assert digits('nine eight seven phir six five four') == []


def test_mobile_pattern_flag():
    hit = phone_hits(words('nau aath saat chhe paanch char teen do ek shunya'))[0]
    assert hit.mobile_pattern and hit.normalized_value == '9876543210'
    other = phone_hits(words('two zero two five five five zero one four six'))[0]
    assert not other.mobile_pattern  # run still detected; exact format not required


def test_bleep_padding_clips_and_merges():
    hit = phone_hits(words('one two three four five six'))[0]
    (s, e), = bleep_intervals([hit], 0.5, 30)
    assert s == 0.0 and e == pytest.approx(hit.t_end + 0.5)


def recorded_windows():
    rows = []
    for i in range(12):
        j = json.loads((ART / f'window_{i:02d}.raw.txt').read_text())
        rows.append((i * 1.5, min(i * 1.5 + 2.0, 18.0), j.get('transcript', '')))
    return rows


def test_windowed_fixture_stitches_to_the_planted_number():
    ws = listen.stitch(recorded_windows())
    hits = phone_hits(ws, 'window')
    assert [h.normalized_value for h in hits] == ['2025550146']  # recorded real responses, no network
    assert 3.0 <= hits[0].t_start and hits[0].t_end <= 9.5


def test_select_times_union_dedupe_cap():
    sel = select_times(10.0, [2.1, 2.2, 5.0], interval_s=1.0, dedupe_s=0.3, cap=30)
    times = [t for t, _ in sel]
    assert all(b - a >= 0.3 for a, b in zip(times, times[1:]))
    assert (5.0, 'scene') in sel and (2.1, 'scene') in sel and (2.0, 'interval') not in sel
    assert len(select_times(100.0, [], cap=30)) == 30


def test_concept_dedupe_merges_similar_and_keeps_baseline():
    def cand(i, prompt, conf, frame):
        return Candidate(candidate_id=f'c{i}', concept=prompt, sam_prompt=prompt, frame_idx=frame,
                         why_identifying='x', confidence=conf, source='spark', model_id='m')
    concepts = discover.build_concepts([cand(1, 'Delivery label', .9, 3), cand(2, 'delivery labels', .6, 9),
                                        cand(3, 'society name board', .7, 4)])
    spark = [c for c in concepts if c.source == 'spark']
    assert len(spark) == 2
    merged = next(c for c in spark if 'delivery' in c.sam_prompt.lower())
    assert merged.candidate_ids == ['c1', 'c2'] and merged.max_confidence == .9 and merged.first_frame_idx == 3
    assert [c.sam_prompt for c in concepts if c.source == 'baseline'] == discover.BASELINE


VALID = '{"items":[{"concept":"delivery label","sam_prompt":"delivery label","why_identifying":"address","confidence":0.8}]}'


def test_discover_valid_invalid_repair_and_empty(tmp_path):
    calls = []

    def ask_ok(path, repair):
        calls.append(repair)
        return VALID, 'm'
    items, mid, err = discover.discover_frame(ask_ok, tmp_path / 'a.jpg')
    assert len(items) == 1 and err is None and calls == [None]

    seq = iter(['not json', VALID])
    items, _, err = discover.discover_frame(lambda p, r: (next(seq), 'm'), tmp_path / 'a.jpg')
    assert len(items) == 1 and err is None

    items, _, err = discover.discover_frame(lambda p, r: ('{"items": [{"bad": 1}]}', 'm'), tmp_path / 'a.jpg')
    assert items == [] and 'invalid JSON' in err  # never invents candidates

    items, _, err = discover.discover_frame(lambda p, r: ('{"items":[]}', 'm'), tmp_path / 'a.jpg')
    assert items == [] and err is None


def test_track_plan_cost_guard():
    def c(i, src, conf):
        return Concept(concept_id=f'{src}-{i}', sam_prompt=f'p{i}', source=src, first_frame_idx=0,
                       candidate_ids=[], max_confidence=conf)
    concepts = [c(i, 'spark', .9 - i * .01) for i in range(12)] + [c('low', 'spark', .2)] + \
               [c(i, 'baseline', 1.0) for i in range(4)]
    run, skipped = track.plan(concepts)
    assert sum(x.source == 'baseline' for x in run) == 4
    assert sum(x.source == 'spark' for x in run) == 10
    reasons = {s.concept_id: s.reason for s in skipped}
    assert len(skipped) == 3 and 'confidence' in reasons['spark-low'] and sum('cap' in r for r in reasons.values()) == 2
