"""Original background bed for the Veil demo, synthesized in code (no third-party music, no license needed).
Calm ambient: warm detuned pads over a 4-chord loop, a soft plucked arpeggio, a sub pulse, and a simple reverb.
Run: .venv/bin/python compose_bed.py SECONDS OUT.wav"""
import sys
import wave

import numpy as np

SR = 48000
BPM = 84
BEAT = 60 / BPM
BAR = 4 * BEAT
# Cmaj9 -> Am9 -> Fmaj9 -> G6/9 (MIDI notes), two bars each
CHORDS = [[48, 55, 59, 62, 64], [45, 52, 55, 59, 60], [41, 48, 52, 55, 57], [43, 50, 52, 57, 59]]
ARP = [[60, 64, 67, 71, 74], [57, 60, 64, 67, 71], [53, 57, 60, 64, 67], [55, 59, 62, 64, 69]]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n, a, r):
    e = np.ones(n)
    ai, ri = int(a * SR), int(r * SR)
    e[:ai] = np.linspace(0, 1, ai) ** 2
    e[-ri:] *= np.linspace(1, 0, ri) ** 1.5
    return e


def pad(note, dur, rng):
    t = np.arange(int(dur * SR)) / SR
    out = np.zeros((len(t), 2))
    for side, det in ((0, -5), (1, 6)):  # detune in cents, slightly different per channel
        f = hz(note) * 2 ** (det / 1200)
        ph = rng.uniform(0, 2 * np.pi)
        s = sum(np.sin(2 * np.pi * f * k * t + ph * k) / k ** 1.6 for k in range(1, 7))  # soft, filtered-saw-like
        out[:, side] = s
    return out * env(len(t), 1.8, 2.2)[:, None]


def pluck(note, dur):
    t = np.arange(int(dur * SR)) / SR
    f = hz(note)
    s = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 5.5)
    return np.stack([s, s], 1) * env(len(t), 0.004, 0.05)[:, None]


def reverb(x, secs=2.2, mix=0.32, seed=3):
    rng = np.random.default_rng(seed)
    n = int(secs * SR)
    ir = rng.standard_normal((n, 2)) * np.exp(-np.linspace(0, 6, n))[:, None]
    ir[:, 1] = np.roll(ir[:, 1], 211)
    wet = np.stack([np.fft.irfft(np.fft.rfft(x[:, c], len(x) + n) * np.fft.rfft(ir[:, c], len(x) + n))[:len(x)] for c in range(2)], 1)
    wet /= np.max(np.abs(wet)) + 1e-9
    return (1 - mix) * x / (np.max(np.abs(x)) + 1e-9) + mix * wet


def compose(seconds):
    rng = np.random.default_rng(7)
    n = int((seconds + 3) * SR)
    mix = np.zeros((n, 2))
    t0, ci = 0.0, 0
    while t0 < seconds + 1:
        chord, arp = CHORDS[ci % 4], ARP[ci % 4]
        dur = 2 * BAR
        start = int(t0 * SR)
        for note in chord:  # pads, overlapping into the next chord for smooth changes
            p = pad(note, dur + 1.5, rng) * 0.11
            end = min(n, start + len(p))
            mix[start:end] += p[:end - start]
        sub = pad(chord[0] - 12, dur + 0.5, rng)[:, :] * 0.10  # sub root
        end = min(n, start + len(sub)); mix[start:end] += sub[:end - start]
        for k in range(16):  # eighth-note arpeggio, very soft, fades in after the first loop
            s = start + int(k * BEAT / 2 * SR)
            if s >= n:
                break
            p = pluck(arp[(k * 3) % 5] + (12 if k % 8 == 7 else 0), BEAT * 1.2) * (0.05 if t0 >= 2 * BAR * 4 else 0.025)
            e = min(n, s + len(p)); mix[s:e] += p[:e - s]
        t0 += dur
        ci += 1
    out = reverb(mix)
    fade = int(2.5 * SR)
    out[:fade] *= np.linspace(0, 1, fade)[:, None]
    end = int(seconds * SR)
    out = out[:end]
    out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return out / np.max(np.abs(out)) * 0.7


if __name__ == '__main__':
    secs, dst = float(sys.argv[1]), sys.argv[2]
    y = compose(secs)
    with wave.open(dst, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((y * 32767).astype(np.int16).tobytes())
    print(f'{dst}: {secs:.1f} s, original synthesized bed ({BPM} bpm, Cmaj9-Am9-Fmaj9-G6/9)')
