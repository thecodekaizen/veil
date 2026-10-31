"""Spoken-digit runs from timed words (English / Hindi / Marathi romanized, Devanagari, ASCII).

A "digit token" is one spoken digit word, one digit of a numeric token ("98765" = 5 tokens), or a
double/triple + digit pair (1 token, 2-3 digits). A run is emitted only if it has >= MIN_DIGITS digits from
>= MIN_TOKENS consecutive digit tokens, so common words ("do minute", "ek baar", "saat baje") do not fire alone.
"""
import unicodedata
from dataclasses import dataclass

from veil.schemas import Word

MAX_GAP_S = 1.5
MIN_DIGITS = 6
MIN_TOKENS = 4

ENGLISH = {'zero': 0, 'oh': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
           'eight': 8, 'nine': 9}
HINDI = {'shunya': 0, 'ek': 1, 'do': 2, 'teen': 3, 'char': 4, 'chaar': 4, 'paanch': 5, 'panch': 5, 'chhe': 6,
         'chhah': 6, 'chheh': 6, 'che': 6, 'saat': 7, 'aath': 8, 'nau': 9}
MARATHI = {'don': 2, 'paach': 5, 'saha': 6}
DEVANAGARI = {'शून्य': 0, 'एक': 1, 'दो': 2, 'तीन': 3, 'चार': 4, 'पांच': 5, 'पाँच': 5, 'छह': 6, 'छः': 6,
              'सात': 7, 'आठ': 8, 'नौ': 9, 'दोन': 2, 'पाच': 5, 'सहा': 6}
WORDS = {**ENGLISH, **HINDI, **MARATHI, **DEVANAGARI}
MULTIPLIERS = {'double': 2, 'triple': 3}
FILLERS = {'uh', 'um', 'umm', 'uhh', 'hmm', 'ah', 'aa', 'matlab', 'haan', 'han', 'ok', 'okay'}
DEVANAGARI_DIGITS = {c: i for i, c in enumerate('०१२३४५६७८९')}


@dataclass
class DigitRun:
    digits: str
    n_tokens: int
    word_indices: list[int]
    t_start: float
    t_end: float


def _clean(text: str) -> str:
    # Drop punctuation/symbols/spaces but keep combining marks (Devanagari matras need them).
    return ''.join(ch for ch in text.lower() if unicodedata.category(ch)[0] not in 'PSZC')


def _numeric(token: str) -> str | None:
    if token and all(c.isdigit() or c in DEVANAGARI_DIGITS for c in token):
        return ''.join(str(DEVANAGARI_DIGITS.get(c, c)) for c in token)
    return None


def digit_runs(words: list[Word]) -> list[DigitRun]:
    runs: list[DigitRun] = []
    cur: dict | None = None

    def close():
        nonlocal cur
        if cur and len(cur['digits']) >= MIN_DIGITS and cur['tokens'] >= MIN_TOKENS:
            runs.append(DigitRun(''.join(cur['digits']), cur['tokens'], cur['idx'], cur['t0'], cur['t1']))
        cur = None

    pending_mult: tuple[int, int] | None = None  # (multiplier, word index)
    for i, w in enumerate(words):
        tok = _clean(w.text)
        if not tok:
            continue
        if tok in MULTIPLIERS:
            pending_mult = (MULTIPLIERS[tok], i)
            continue
        digits, ntok = None, 0
        if tok in WORDS:
            digits, ntok = [str(WORDS[tok])], 1
        elif (num := _numeric(tok)) is not None:
            digits, ntok = list(num), len(num)
        if digits is not None and pending_mult and len(digits) == 1:
            digits, ntok = digits * pending_mult[0], 1
        idx = ([pending_mult[1]] if pending_mult and digits else []) + [i]
        mult_idx = pending_mult
        pending_mult = None
        if digits is None:
            if tok in FILLERS:
                continue
            close()
            continue
        if cur and w.t_start - cur['t1'] > MAX_GAP_S:
            close()
        if cur is None:
            first_t = words[mult_idx[1]].t_start if mult_idx else w.t_start
            cur = {'digits': [], 'tokens': 0, 'idx': [], 't0': first_t, 't1': w.t_end}
        cur['digits'].extend(digits)
        cur['tokens'] += ntok
        cur['idx'].extend(idx)
        cur['t1'] = max(cur['t1'], w.t_end)
    close()
    return runs
