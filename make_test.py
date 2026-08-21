#!/usr/bin/env python3
"""Generate a synthetic bassline with KNOWN pitches, to validate the pipeline."""
import numpy as np
import soundfile as sf

SR = 44100
BPM = 100
BEAT = 60.0 / BPM

# ground truth: E1 walk-up, MIDI numbers
TRUTH = [28, 31, 33, 35, 36, 35, 33, 31, 28, 28, 40, 38, 36, 33, 31, 28]


def note(midi, dur, sr=SR):
    f = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    # bass timbre: fundamental + a few harmonics, decaying
    w = np.zeros_like(t)
    for h, amp in [(1, 1.0), (2, 0.45), (3, 0.22), (4, 0.10)]:
        w += amp * np.sin(2 * np.pi * f * h * t)
    env = np.exp(-3.0 * t / dur) * np.minimum(1, t / 0.005)
    return w * env * 0.35


sig = np.concatenate([note(m, BEAT) for m in TRUTH])
sig = np.tile(sig, 2)                       # two passes
sig /= np.max(np.abs(sig)) * 1.05
sf.write("test_bass.wav", sig.astype(np.float32), SR)

with open("test_truth.txt", "w") as f:
    f.write(" ".join(map(str, TRUTH * 2)))

print(f"wrote test_bass.wav  {len(sig)/SR:.2f}s  {len(TRUTH)*2} notes  bpm={BPM}")
