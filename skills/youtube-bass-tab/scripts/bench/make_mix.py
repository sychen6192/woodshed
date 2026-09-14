"""Synthesize a 'song' with a known bass line buried in a mix, to test separation.

    python scripts/bench/make_mix.py <out_dir>

Writes <out>/mix.wav (bass + kick + hats + pad chords) and <out>/bass_only.wav,
plus truth.json with the bass note list, tempo and downbeat.
"""
import json, os, sys
import numpy as np
import soundfile as sf

SR = 44100
np.random.seed(0)          # the humanization must be the same on every machine
BPM = 96.0
BEAT = 60.0 / BPM
E8 = BEAT / 2
BAR = BEAT * 4
DOWNBEAT = 1.10          # bar 1 starts here; before it there is a pad-only intro
BARS = 12

# I-vi-IV-V in G, one bar each, bass plays root + fifth + octave walk in eighths
CHORDS = [("G", 31, [31, 31, 38, 35, 31, 38, 35, 33]),     # G1 ...
          ("Em", 28, [28, 28, 35, 31, 28, 35, 31, 30]),
          ("C", 36, [36, 36, 43, 40, 36, 43, 40, 38]),
          ("D", 38, [38, 38, 45, 42, 38, 45, 42, 40])]


def tone(f, n, harm, decay, attack=0.004):
    t = np.arange(n) / SR
    env = np.exp(-t * decay) * np.minimum(1, t / attack)
    return sum(a * np.sin(2 * np.pi * f * h * t) for h, a in harm) * env


def midi_f(m):
    return 440.0 * 2 ** ((m - 69) / 12)


total = DOWNBEAT + BARS * BAR + 1.5
n_total = int(SR * total)
bass = np.zeros(n_total, np.float32)
drums = np.zeros(n_total, np.float32)
pad = np.zeros(n_total, np.float32)
truth = []

for b in range(BARS):
    name, root, line = CHORDS[b % 4]
    t0 = DOWNBEAT + b * BAR
    # bass: eighths, accent on 1, slight humanization
    for i, p in enumerate(line):
        t = t0 + i * E8 + np.random.uniform(-0.008, 0.008)
        vel = 1.0 if i == 0 else 0.72
        n = int(SR * E8 * 0.92)
        sig = tone(midi_f(p), n, [(1, 1.0), (2, .55), (3, .3), (4, .15), (5, .08)], 4.5) * vel
        s = int(t * SR); bass[s:s + n] += sig.astype(np.float32)
        truth.append({"start": round(t, 4), "pitch": p, "chord": name})
    # drums: kick on 1 and 3, snare on 2 and 4, hats on eighths
    for k in range(4):
        t = t0 + k * BEAT
        s = int(t * SR)
        if k in (0, 2):                      # kick: pitched sweep 120->45 Hz, sits ON the bass
            n = int(SR * 0.25); tt = np.arange(n) / SR
            f = 45 + 75 * np.exp(-tt * 28)
            kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 14)
            drums[s:s + n] += (kick * 0.9).astype(np.float32)
        else:                                # snare: noise burst
            n = int(SR * 0.14)
            snare = np.random.randn(n) * np.exp(-np.arange(n) / SR * 30)
            drums[s:s + n] += (snare * 0.35).astype(np.float32)
    for k in range(8):                       # hats
        s = int((t0 + k * E8) * SR); n = int(SR * 0.04)
        hat = np.random.randn(n) * np.exp(-np.arange(n) / SR * 120)
        drums[s:s + n] += (hat * 0.18).astype(np.float32)
    # pad: triad two octaves up, held for the bar (starts one bar early as intro)
    n = int(SR * BAR)
    for iv in (0, 4 if name != "Em" else 3, 7):
        p = root + 24 + iv
        pad_sig = tone(midi_f(p), n, [(1, .5), (2, .25), (3, .12)], 0.3, attack=0.08)
        pad[int(t0 * SR):int(t0 * SR) + n] += (pad_sig * 0.28).astype(np.float32)

# intro: one bar of pad only before the downbeat, so bar 1 is not t=0
n = int(SR * DOWNBEAT)
pad[:n] += (tone(midi_f(31 + 24), n, [(1, .5), (2, .25)], 0.3, attack=0.08) * 0.28).astype(np.float32)

mix = bass * 0.9 + drums * 0.8 + pad
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
for name, sig in (("mix.wav", mix), ("bass_only.wav", bass)):
    sig = sig / (np.abs(sig).max() * 1.1)
    sf.write(os.path.join(out, name), np.stack([sig, sig], 1), SR)     # stereo, like a real file
json.dump({"bpm": BPM, "downbeat": DOWNBEAT, "bars": BARS, "notes": truth},
          open(os.path.join(out, "truth.json"), "w"), indent=1)
print(f"wrote {out}/mix.wav ({total:.1f}s) and bass_only.wav: bpm={BPM} downbeat={DOWNBEAT}s "
      f"notes={len(truth)}  range {min(t['pitch'] for t in truth)}-{max(t['pitch'] for t in truth)}")
