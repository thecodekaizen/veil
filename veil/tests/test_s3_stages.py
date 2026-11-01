import json
import re
from pathlib import Path

import numpy as np

from veil import report
from veil.schemas import (AppliedRegion, AuditArtifact, Check, Finding, RedactArtifact, RegionFrame)
from veil.stages import audit
from veil.validators.pii import bleep_intervals

BANNED = re.compile(r'\b(safe|certified|guaranteed|leak-free)\b', re.I)
ROOT = Path(__file__).resolve().parents[1]


def test_wording_guard_sources():
    files = [ROOT / 'src/veil/report.py', ROOT / 'src/veil/stages/audit.py', *(ROOT / 'src/veil/prompts').glob('*.txt')]
    files += [p for p in (ROOT / 'web/src').rglob('*') if p.is_file() and p.suffix in {'.ts', '.tsx', '.css', '.html'}] \
        if (ROOT / 'web/src').exists() else []
    bad = {str(f): BANNED.findall(f.read_text()) for f in files if BANNED.search(f.read_text())}
    assert not bad


def test_overlap_and_visual_status(tmp_path):
    assert audit._overlap((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert audit._overlap((0, 0, 10, 10), (5, 0, 15, 10)) == 0.5
    assert audit._overlap((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0


def test_receipt_renders_and_has_footer(tmp_path):
    from veil.schemas import Concept, DiscoverArtifact
    (tmp_path / 'discover.json').write_text(DiscoverArtifact(prompt_version='v', model_id='m', candidates=[], errors=[],
        concepts=[Concept(concept_id='c', sam_prompt='face', source='spark', first_frame_idx=0, candidate_ids=[], max_confidence=.5)]).model_dump_json())
    (tmp_path / 'redact.json').write_text(RedactArtifact(input_sha256='a' * 64, output_path='output.mp4', output_sha256='b' * 64,
        pad_px=12, action='cover', regions=[], muted_intervals=[]).model_dump_json())
    findings = [Finding(finding_id='a', kind='visual', label='face', source='spark', status='COVERED', reasons=['x']),
                Finding(finding_id='b', kind='audio', label='n', source='voice', status='UNRESOLVED', reasons=['y']),
                Finding(finding_id='c', kind='visual', label='z', source='spark', status='NOT_CHECKED', reasons=['cap'])]
    (tmp_path / 'audit.json').write_text(AuditArtifact(findings=findings, limitations=['l'], concepts_without_masks=[],
        checks=[Check(check_id='k', description='d', status='NOT_CHECKED')]).model_dump_json())
    html = report.render(tmp_path).read_text()
    assert report.FOOTER in html and 'UNRESOLVED' in html and 'NOT_CHECKED' in html
    assert '1 unresolved finding(s)' in html and not BANNED.search(html)
    assert 'No unresolved risks found' not in html


def test_headline_when_clean(tmp_path):
    test_receipt_renders_and_has_footer(tmp_path)
    a = AuditArtifact.model_validate_json((tmp_path / 'audit.json').read_text())
    a.findings = [f for f in a.findings if f.status == 'COVERED']
    a.checks = []
    (tmp_path / 'audit.json').write_text(a.model_dump_json())
    assert 'No unresolved risks found by the checks listed below.' in report.render(tmp_path).read_text()


def test_audit_visual_covered_and_gap(tmp_path):
    import cv2
    from veil.schemas import (Concept, DiscoverArtifact, MaskFrame, Masklet, TrackArtifact)
    out = tmp_path / 'output.mp4'
    w = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*'mp4v'), 10, (64, 64))
    for i in range(6):
        img = np.full((64, 64, 3), 200, np.uint8)
        if i != 3:
            img[10:30, 10:30] = 0  # frame 3 is left uncovered
        w.write(img)
    w.release()
    disc = DiscoverArtifact(prompt_version='v', model_id='m', candidates=[], errors=[], concepts=[
        Concept(concept_id='c', sam_prompt='face', source='spark', first_frame_idx=0, candidate_ids=[], max_confidence=.9)])
    frames = [MaskFrame(frame_idx=i, bbox=(10, 10, 30, 30)) for i in (0, 1, 2, 3, 4, 5)]
    track = TrackArtifact(model_id='s', linking='model', masklets=[Masklet(concept_id='c', track_id='t', frames=frames)], skipped_concepts=[])
    red = RedactArtifact(input_sha256='a', output_path='output.mp4', output_sha256='b', pad_px=0, action='cover', muted_intervals=[],
        regions=[AppliedRegion(concept_id='c', track_id='t', source='spark', sam_prompt='face',
                               frames=[RegionFrame(frame_idx=i, box=(10, 10, 30, 30)) for i in range(6)])])
    findings, empty = audit._visual_findings(disc, track, red, out)
    assert findings[0].status == 'UNRESOLVED' and 'cover not found' in findings[0].reasons[0] and not empty
    track.masklets[0].frames = [f for f in frames if f.frame_idx != 2]  # gap inside span
    findings, _ = audit._visual_findings(disc, track, red, out)
    assert any('no mask' in r for r in findings[0].reasons)


def test_bleep_union():
    assert bleep_intervals([], 0.5, 10) == []


def _masklet(first, last, box=(10, 10, 30, 30)):
    from veil.schemas import MaskFrame, Masklet
    return Masklet(concept_id='c', track_id='c:0', frames=[MaskFrame(frame_idx=i, bbox=box) for i in range(first, last + 1)])


def test_temporal_pad_fills_ends_and_small_gaps():
    from veil.stages.extend import temporal_pad
    from veil.schemas import MaskFrame, Masklet
    m = Masklet(concept_id='c', track_id='t', frames=[MaskFrame(frame_idx=i, bbox=(0, 0, 5, 5)) for i in (10, 11, 15)])
    out = {f.frame_idx: f.origin for f in temporal_pad(m, 30).frames}
    assert min(out) == 7 and max(out) == 18 and out[10] == 'sam' and out[13] == 'temporal_pad' and out[12] == 'temporal_pad'
    assert set(range(7, 19)) == set(out)


def test_extend_holds_back_when_reverse_fails():
    from veil.stages.extend import extend_masklet

    def boom(*a):
        raise RuntimeError('no')
    m, ext = extend_masklet(_masklet(4, 9), 0, 'x', boom, 100)
    assert ext.method == 'held_back' and 'failed' in ext.note
    assert [f.frame_idx for f in m.frames] == list(range(0, 10))
    assert {f.origin for f in m.frames if f.frame_idx < 4} == {'held_back'}


def test_extend_uses_reversed_sam_when_it_overlaps():
    from veil.schemas import MaskFrame
    from veil.stages.extend import extend_masklet
    rev = {'0': {i: {'box': [10, 10, 30, 30], 'frame': MaskFrame(frame_idx=i, bbox=(10, 10, 30, 30))} for i in range(0, 10)}}
    m, ext = extend_masklet(_masklet(4, 9), 0, 'x', lambda *a: rev, 100)
    assert ext.method == 'sam_reversed'
    assert {f.origin for f in m.frames if f.frame_idx < 4} == {'sam_reversed'}


def test_extend_noop_and_start_rule():
    from veil.stages.extend import extend_masklet
    m, ext = extend_masklet(_masklet(0, 5), 0, 'x', None, 100)
    assert ext.method == 'none' and len(m.frames) == 6
    m, ext = extend_masklet(_masklet(40, 50), 20, 'x', None, 100)  # later than discovery keyframe 20
    assert ext.method == 'held_back' and min(f.frame_idx for f in m.frames) == 20


def test_gate_scorer_helpers():
    from gate import score_gate as sg
    assert sg.edit_distance('2025550146', '2145550146') == 2 and sg.edit_distance('a', 'a') == 0
    assert sg.range_frames([(0.0, 0.5)], 10) == [0, 1, 2, 3, 4, 5]
    assert sg.frame_of(1.26, 10) == 13
    g = {k: {'ok': True} for k in ('G1', 'G2', 'G3', 'G4a', 'G4b')}
    assert sg.verdict_of(g) == 'PASS'
    g['G3']['ok'] = False
    assert sg.verdict_of(g) == 'FAIL'


def test_gate_scorer_not_run_without_labels(tmp_path):
    from gate import score_gate as sg
    r = sg.score(tmp_path / 'labels', tmp_path / 'runs', tmp_path / 'clips')
    assert r['verdict'] == 'NOT RUN' and sg.render_md(r).startswith('# GATE: NOT RUN')


def test_gate_scorer_audio_and_mask_iou():
    from gate import score_gate as sg
    from gate.labels_schema import AudioSpan, Leak
    from veil.schemas import ListenArtifact, MaskData, MaskFrame, SpokenPII
    import base64
    leak = Leak(leak_id='A1', kind='audio', concept='n', in_baseline=False,
                audio=AudioSpan(text='x', digits='2025550146', t_start=5.0, t_end=9.0))
    pii = SpokenPII(kind='phone', normalized_value='2145550146', t_start=4.5, t_end=9.5, word_indices=[0], validator='v',
                    precision='window', mobile_pattern=False)
    la = ListenArtifact(model_id='m', method='windowed', window_s=2, overlap_s=.5, bleep_pad_s=.5, words=[], transcript_text='',
                        pii=[pii], bleep_intervals=[(4.0, 10.0)])
    r = sg.score_audio(leak, la)
    assert r['g4a_detected'] and not r['exact'] and r['edit_distance'] == 2
    assert r['coverage_pct'] == 100.0 and r['over_cover_s'] == 2.0 and r['g4b_ok']
    la.bleep_intervals = [(4.0, 12.0)]
    assert not sg.score_audio(leak, la)['g4b_ok']  # over-cover 4 s > 2.5 s
    import numpy as np
    bits = np.packbits(np.ones(100, np.uint8)).tobytes()  # 10x10 solid mask at (0,0)
    mf = MaskFrame(frame_idx=0, bbox=(0, 0, 10, 10), mask=MaskData(width=10, height=10, packed_b64=base64.b64encode(bits).decode(),
                                                                    bounds=(0, 0, 10, 10)))
    assert sg.mask_iou(mf, (0, 0, 10, 10), 50, 50) == 1.0
    assert abs(sg.mask_iou(mf, (5, 0, 15, 10), 50, 50) - 50 / 150) < 1e-9
    assert sg.mask_iou(MaskFrame(frame_idx=0, bbox=(0, 0, 1, 1)), (0, 0, 10, 10), 50, 50) == 0.0
