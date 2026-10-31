"""Voice Transcribe timing/biasing smoke test on the synthetic smoke-001 audio (no real person's audio).

Records raw responses to artifacts/voice-timing-001/. Tests: SSE streaming events, file-mode keyword
biasing and languageBias, and windowed transcription (2 s windows, 0.5 s overlap). Refuses to overwrite.
"""
import json, os, re, sys, time, wave
from pathlib import Path
import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'voice-timing-001'
AUDIO = ROOT / 'artifacts' / 'smoke-001' / 'audio.wav'
URL = 'https://api.meta.ai/v1/asr/transcribe'
MODEL = 'muse-voice-transcribe-1.0'
KEYWORDS = ['phone number', 'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
NUMWORDS = set('zero oh one two three four five six seven eight nine ten'.split())
TRUTH = '2025550146'  # synthetic fixture value (ground-truth.json: 202-555-0146)


def key():
    k = os.getenv('MODEL_API_KEY')
    for line in (ROOT.parent / '.env').read_text().splitlines():
        if line.startswith('MODEL_API_KEY='):
            k = line.split('=', 1)[1].strip().strip('"\'')
    return k


def wav_bytes(samples, rate):
    import io
    b = io.BytesIO()
    with wave.open(b, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(samples.tobytes())
    return b.getvalue()


def call(api_key, audio_bytes, request, accept='application/json'):
    t = time.monotonic()
    r = httpx.post(URL, headers={'Authorization': 'Bearer ' + api_key, 'Accept': accept},
                   files={'request': (None, json.dumps(request), 'application/json'),
                          'audio': ('audio.wav', audio_bytes, 'audio/wav')}, timeout=120)
    return r, int((time.monotonic() - t) * 1000)


WORD_DIGIT = {'zero': '0', 'oh': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
              'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'}


def digits(text):
    """ASCII digits plus spelled-out English digit words (keyword biasing makes the model spell them)."""
    return ''.join(t if t.isdigit() else WORD_DIGIT.get(t, '') for t in re.findall(r'\d+|[a-z]+', text.lower()))


def main():
    if OUT.exists():
        sys.exit('refusing to overwrite ' + str(OUT))
    OUT.mkdir(parents=True)
    k = key()
    with wave.open(str(AUDIO)) as w:
        rate = w.getframerate(); pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    full = AUDIO.read_bytes()
    summary = {'audio': 'artifacts/smoke-001/audio.wav', 'rate': rate, 'truth_digits': TRUTH, 'calls': []}

    def record(name, r, ms, extra=None):
        (OUT / f'{name}.raw.txt').write_text(r.text)
        row = {'name': name, 'status': r.status_code, 'latency_ms': ms, 'bytes_sent': len(full), **(extra or {})}
        summary['calls'].append(row); return row

    # 1. SSE streaming events from the file endpoint: any timing field besides audioProcessedMs?
    r, ms = call(k, full, {'model': MODEL, 'mode': 'ENDPOINTING', 'audioEncoding': 'WAV', 'languageBias': ['English'],
                           'partialMode': 'CUMULATIVE', 'emitAudioProgress': True}, 'text/event-stream')
    events = [json.loads(l[5:]) for l in r.text.splitlines() if l.startswith('data:') and l[5:].strip().startswith('{')]
    fields = sorted({f for e in events for f in e})
    record('sse_cumulative', r, ms, {'event_types': sorted({e.get('type', '?') for e in events}), 'fields_seen': fields,
                                     'n_events': len(events)})

    # 2. file mode variants: baseline / keywords / languageBias English+Hindi
    base = {'model': MODEL, 'mode': 'ENDPOINTING', 'audioEncoding': 'WAV'}
    for name, extra in [('file_baseline', {'languageBias': ['English']}),
                        ('file_keywords', {'languageBias': ['English'], 'keywords': KEYWORDS}),
                        ('file_en_hi', {'languageBias': ['English', 'Hindi']}),
                        ('file_en_hi_keywords', {'languageBias': ['English', 'Hindi'], 'keywords': KEYWORDS})]:
        r, ms = call(k, full, {**base, **extra})
        j = r.json() if r.status_code == 200 else {}
        record(name, r, ms, {'transcript': j.get('transcript'), 'digits': digits(j.get('transcript', '')),
                             'digit_match': digits(j.get('transcript', '')) == TRUTH,
                             'turns': [(t['startMs'], t['endMs']) for t in j.get('turns', [])]})

    # 3. windowed: 2.0 s windows, 0.5 s overlap (stride 1.5 s), default PUSH_TO_TALK, keywords on
    win, hop = int(2.0 * rate), int(1.5 * rate)
    windows = []
    for i, s in enumerate(range(0, len(pcm) - int(0.5 * rate), hop)):
        seg = pcm[s:s + win]
        r, ms = call(k, wav_bytes(seg, rate), {'model': MODEL, 'audioEncoding': 'WAV', 'languageBias': ['English'],
                                               'keywords': KEYWORDS})
        t0 = s / rate; t1 = t0 + len(seg) / rate
        text = r.json().get('transcript', '') if r.status_code == 200 else ''
        hit = bool(re.search(r'\d', text)) or any(w in NUMWORDS for w in re.findall(r'[a-z]+', text.lower()))
        (OUT / f'window_{i:02d}.raw.txt').write_text(r.text)
        windows.append({'i': i, 't0': round(t0, 2), 't1': round(t1, 2), 'status': r.status_code, 'latency_ms': ms,
                        'transcript': text, 'digit_hit': hit})
    summary['windows'] = windows
    hits = [w for w in windows if w['digit_hit']]
    if hits:
        # Intersection of overlapping hit windows is tighter than the union; report both.
        summary['windowed_union_s'] = [hits[0]['t0'], hits[-1]['t1']]
    # Energy-based speech segments as a local, model-free reference for the spoken span.
    x = pcm.astype(np.float32) / 32768; step = int(0.05 * rate)
    rms = np.array([np.sqrt(np.mean(x[i:i + step] ** 2)) for i in range(0, len(x) - step, step)])
    on = rms > 0.02
    segs, start = [], None
    for i, v in enumerate(on):
        if v and start is None: start = i
        if not v and start is not None:
            segs.append([round(start * .05, 2), round(i * .05, 2)]); start = None
    summary['energy_speech_segments_s'] = segs
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({k2: v for k2, v in summary.items() if k2 not in ('windows',)}, indent=1)[:3500])
    for w in windows:
        print(w['i'], w['t0'], w['t1'], w['status'], repr(w['transcript']))


main()
