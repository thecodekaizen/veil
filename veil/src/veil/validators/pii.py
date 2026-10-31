"""Spoken-PII classification on top of digit runs."""
import re

from veil.schemas import SpokenPII, Word
from veil.validators.spoken_digits import digit_runs

MOBILE = re.compile(r'^(?:\+?91|0)?[6-9]\d{9}$')


def phone_hits(words: list[Word], precision: str = 'window') -> list[SpokenPII]:
    """Phone-like runs (>= 6 digits from >= 4 consecutive digit tokens). Exact digits are not required;
    `mobile_pattern` records whether the digits also match an Indian mobile number."""
    return [SpokenPII(kind='phone', normalized_value=r.digits, t_start=r.t_start, t_end=r.t_end,
                      word_indices=r.word_indices, validator='spoken_digit_run_v1', precision=precision,
                      mobile_pattern=bool(MOBILE.match(r.digits)))
            for r in digit_runs(words)]


def bleep_intervals(pii: list[SpokenPII], pad_s: float, duration_s: float) -> list[tuple[float, float]]:
    """Union of PII intervals padded by pad_s on each side, clipped to [0, duration_s]."""
    spans = sorted((max(0.0, p.t_start - pad_s), min(duration_s, p.t_end + pad_s)) for p in pii)
    merged: list[list[float]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]
