"""Listen: windowed Voice Transcribe (the API returns turn-level timing only) + spoken-PII validators.

Method (docs/api_notes.md): 2 s windows with 0.5 s overlap, PUSH_TO_TALK, keyword bias. Words inherit their
window's time span; a word that appears in two consecutive windows (de-duplicated across the overlap) is
narrowed to the overlap. PII timing therefore has window precision (~2 s), not word precision.
"""
import re
import wave
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import numpy as np

from veil.schemas import ListenArtifact, Word
from veil.validators.pii import bleep_intervals, phone_hits

WINDOW_S = 2.0
OVERLAP_S = 0.5
MODEL_ID = 'muse-voice-transcribe-1.0'
KEYWORDS = ['phone number', 'number', 'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
LANGUAGE_BIAS = ['English', 'Hindi']  # Hinglish target; untested on real Hinglish audio (docs/api_notes.md)
MAX_OVERLAP_TOKENS = 4
CONCURRENCY = 4

Transcribe = Callable[[bytes], str]  # WAV bytes -> transcript text


def window_spans(duration_s: float, window_s: float = WINDOW_S, overlap_s: float = OVERLAP_S):
    hop = window_s - overlap_s
    t = 0.0
    while t < duration_s - overlap_s:
        yield t, min(t + window_s, duration_s)
        t += hop


def tokens(text: str) -> list[str]:
    return re.findall(r'[\wऀ-ॿ]+', text, flags=re.UNICODE)


def stitch(windows: list[tuple[float, float, str]]) -> list[Word]:
    """Concatenate window transcripts, dropping tokens repeated across the 0.5 s overlap.
    Limitation: a genuine repeated digit at an overlap boundary is dropped too."""
    words: list[Word] = []
    prev_tokens: list[str] = []
    for t0, t1, text in windows:
        toks = tokens(text)
        drop = 0
        for k in range(min(MAX_OVERLAP_TOKENS, len(prev_tokens), len(toks)), 0, -1):
            if [x.lower() for x in prev_tokens[-k:]] == [x.lower() for x in toks[:k]]:
                drop = k
                break
        if drop:  # these tokens were spoken in the overlap: narrow them
            for w in words[-drop:]:
                w.t_start = max(w.t_start, t0)
        for tok in toks[drop:]:
            words.append(Word(text=tok, t_start=t0, t_end=t1))
        if toks:
            prev_tokens = toks
    return words


def run(wav_path, transcribe: Transcribe, bleep_pad_s: float) -> ListenArtifact:
    with wave.open(str(wav_path)) as w:
        rate = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    duration = len(pcm) / rate
    spans = list(window_spans(duration))

    def one(span):
        t0, t1 = span
        seg = pcm[int(t0 * rate):int(t1 * rate)]
        import io
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate); out.writeframes(seg.tobytes())
        return t0, t1, transcribe(buf.getvalue())

    with ThreadPoolExecutor(CONCURRENCY) as pool:
        windows = list(pool.map(one, spans))
    words = stitch(windows)
    pii = phone_hits(words, precision='window')
    return ListenArtifact(model_id=MODEL_ID, method='windowed', window_s=WINDOW_S, overlap_s=OVERLAP_S,
                          bleep_pad_s=bleep_pad_s, words=words, transcript_text=' '.join(w.text for w in words),
                          pii=pii, bleep_intervals=bleep_intervals(pii, bleep_pad_s, duration))


def make_transcribe(api_key: str, ledger, name_prefix: str = 'listen') -> Transcribe:
    import itertools
    import httpx
    counter = itertools.count()

    def transcribe(wav: bytes) -> str:
        name = f'{name_prefix}-w{next(counter):03d}'
        start = ledger.begin(name, MODEL_ID, '/v1/asr/transcribe', f'{len(wav)} byte WAV window')
        try:
            req = {'model': MODEL_ID, 'audioEncoding': 'WAV', 'languageBias': LANGUAGE_BIAS, 'keywords': KEYWORDS}
            import json
            r = httpx.post('https://api.meta.ai/v1/asr/transcribe', headers={'Authorization': 'Bearer ' + api_key},
                           files={'request': (None, json.dumps(req), 'application/json'),
                                  'audio': ('audio.wav', wav, 'audio/wav')}, timeout=120)
            r.raise_for_status()
            ledger.finish(name, start, estimated_usd=len(wav) / 48000 * .18 / 3600)
            return r.json().get('transcript', '')
        except Exception as exc:
            ledger.fail(name, start, exc)
            raise
    return transcribe
