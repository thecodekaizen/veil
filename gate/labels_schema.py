"""Pydantic schema for gate label files (gate/labels/*.json). See gate/labels/SCHEMA.md."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class RefBox(Strict):
    """Source-video pixel coordinates (top-left origin) at time t_s."""
    t_s: FiniteFloat = Field(ge=0)
    x: FiniteFloat = Field(ge=0)
    y: FiniteFloat = Field(ge=0)
    w: FiniteFloat = Field(gt=0)
    h: FiniteFloat = Field(gt=0)


class AudioSpan(Strict):
    text: str
    digits: str
    t_start: FiniteFloat = Field(ge=0)
    t_end: FiniteFloat = Field(ge=0)

    @model_validator(mode='after')
    def valid(self):
        if not re.fullmatch(r'\d{10}', self.digits):
            raise ValueError('audio.digits must be exactly 10 ASCII digits')
        if self.t_end <= self.t_start:
            raise ValueError('audio.t_end must be after t_start')
        return self


def _check_ranges(ranges: list[tuple[float, float]]) -> None:
    for start, end in ranges:
        if start < 0 or end <= start:
            raise ValueError(f'invalid visible range [{start}, {end}]')


class Leak(Strict):
    leak_id: str = Field(min_length=1)
    kind: Literal['visual', 'audio']
    concept: str = Field(min_length=1)
    # Would the baseline prompts (face / license plate / phone screen / paper document) cover it?
    in_baseline: bool
    visible_ranges: list[tuple[FiniteFloat, FiniteFloat]] = []
    ref_boxes: list[RefBox] = []
    audio: AudioSpan | None = None

    @model_validator(mode='after')
    def valid(self):
        _check_ranges(self.visible_ranges)
        if self.kind == 'visual':
            if not self.visible_ranges:
                raise ValueError('visual leak needs visible_ranges')
            if not 2 <= len(self.ref_boxes) <= 3:
                raise ValueError('visual leak needs 2-3 ref_boxes')
            if self.audio is not None:
                raise ValueError('visual leak must not have audio')
        else:
            if self.audio is None:
                raise ValueError('audio leak needs audio')
            if self.ref_boxes:
                raise ValueError('audio leak must not have ref_boxes')
        return self


class SafeControl(Strict):
    control_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    visible_ranges: list[tuple[FiniteFloat, FiniteFloat]]
    ref_boxes: list[RefBox]

    @model_validator(mode='after')
    def valid(self):
        _check_ranges(self.visible_ranges)
        if not self.visible_ranges or not self.ref_boxes:
            raise ValueError('safe control needs visible_ranges and ref_boxes')
        return self


class Labels(Strict):
    clip_id: str = Field(min_length=1)
    clip_sha256: str
    fps: FiniteFloat = Field(gt=0)
    leaks: list[Leak]
    safe_controls: list[SafeControl] = []

    @model_validator(mode='after')
    def valid(self):
        if not re.fullmatch(r'[0-9a-f]{64}', self.clip_sha256):
            raise ValueError('clip_sha256 must be 64 lowercase hex chars')
        ids = [leak.leak_id for leak in self.leaks] + [c.control_id for c in self.safe_controls]
        if len(ids) != len(set(ids)):
            raise ValueError('leak_id / control_id values must be unique within a clip')
        return self
