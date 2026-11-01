"""Pydantic artifacts for the open-vocabulary stages (keyframes, discover, track, listen)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Keyframe(Strict):
    frame_idx: int = Field(ge=0)
    t_s: FiniteFloat = Field(ge=0)
    path: str
    reason: Literal['scene', 'interval']


class KeyframeArtifact(Strict):
    input_sha256: str
    fps: FiniteFloat
    width: int
    height: int
    duration_s: FiniteFloat
    keyframes: list[Keyframe]


class Candidate(Strict):
    candidate_id: str
    concept: str
    sam_prompt: str
    frame_idx: int = Field(ge=0)
    why_identifying: str
    confidence: FiniteFloat = Field(ge=0, le=1)
    source: Literal['spark', 'baseline']
    model_id: str


class Concept(Strict):
    concept_id: str
    sam_prompt: str
    source: Literal['spark', 'baseline']
    first_frame_idx: int = Field(ge=0)
    candidate_ids: list[str]
    max_confidence: FiniteFloat = Field(ge=0, le=1)
    why_identifying: str = ''


class DiscoverError(Strict):
    frame_idx: int
    error: str


class DiscoverArtifact(Strict):
    prompt_version: str
    model_id: str
    candidates: list[Candidate]
    concepts: list[Concept]
    errors: list[DiscoverError]


class MaskData(Strict):
    """1-bit mask crop (np.packbits, row-major) placed at bounds [left, top, right, bottom] in source pixels."""
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    packed_b64: str
    bounds: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]


class MaskFrame(Strict):
    frame_idx: int = Field(ge=0)
    bbox: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]  # left, top, right, bottom, source pixels
    score: FiniteFloat | None = None  # SAM confidence was null in every observed response
    mask: MaskData | None = None
    origin: Literal['sam', 'sam_reversed', 'held_back', 'temporal_pad'] = 'sam'


class Masklet(Strict):
    concept_id: str
    track_id: str
    frames: list[MaskFrame]


class Extension(Strict):
    concept_id: str
    track_id: str
    method: Literal['sam_reversed', 'held_back', 'none']
    from_frame: int
    to_frame: int
    note: str = ''


class SkippedConcept(Strict):
    concept_id: str
    sam_prompt: str
    source: Literal['spark', 'baseline']
    reason: str


class TrackArtifact(Strict):
    model_id: str
    linking: Literal['model', 'code_iou']
    masklets: list[Masklet]
    skipped_concepts: list[SkippedConcept]
    notes: str = ''
    extensions: list[Extension] = Field(default_factory=list)


class Word(Strict):
    text: str
    t_start: FiniteFloat
    t_end: FiniteFloat


class SpokenPII(Strict):
    kind: Literal['phone']
    normalized_value: str
    t_start: FiniteFloat
    t_end: FiniteFloat
    word_indices: list[int]
    validator: str
    precision: Literal['word', 'window', 'segment', 'window_voiced']
    mobile_pattern: bool


class ListenArtifact(Strict):
    model_id: str
    method: Literal['windowed', 'turn']
    window_s: FiniteFloat
    overlap_s: FiniteFloat
    bleep_pad_s: FiniteFloat
    words: list[Word]
    transcript_text: str
    pii: list[SpokenPII]
    bleep_intervals: list[tuple[FiniteFloat, FiniteFloat]]


Status = Literal['COVERED', 'UNRESOLVED', 'NOT_CHECKED']


class RegionFrame(Strict):
    frame_idx: int = Field(ge=0)
    box: tuple[int, int, int, int]  # left, top, right, bottom of the applied cover, source pixels (padding included)


class AppliedRegion(Strict):
    concept_id: str
    track_id: str
    source: Literal['spark', 'baseline']
    sam_prompt: str
    frames: list[RegionFrame]


class RedactArtifact(Strict):
    """The region map actually applied to the output, so the audit never trusts model state."""
    input_sha256: str
    output_path: str
    output_sha256: str
    pad_px: int
    action: Literal['cover']
    regions: list[AppliedRegion]
    muted_intervals: list[tuple[FiniteFloat, FiniteFloat]]


class Check(Strict):
    check_id: str
    description: str
    status: Literal['RAN', 'NOT_CHECKED']
    detail: str = ''


class Finding(Strict):
    finding_id: str
    kind: Literal['visual', 'audio', 'output_check']
    label: str
    source: Literal['spark', 'baseline', 'voice', 'ocr']
    status: Status
    reasons: list[str]
    evidence: dict = Field(default_factory=dict)


class AuditArtifact(Strict):
    findings: list[Finding]
    checks: list[Check]
    concepts_without_masks: list[str]
    limitations: list[str]
