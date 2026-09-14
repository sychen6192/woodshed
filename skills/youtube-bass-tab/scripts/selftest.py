#!/usr/bin/env python3
"""selftest.py - verify the youtube-bass-tab install without downloading anything.

Synthesizes a 2-bar bassline with 16 known notes, runs basstab.sh on it
(skipping demucs), and checks that the tab comes out with ~16 notes.
Run it with the venv's python:  ~/.venvs/basstab/bin/python scripts/selftest.py
"""
import json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LINE = [28, 28, 31, 33, 35, 33, 31, 28, 33, 33, 36, 38, 40, 38, 36, 33]  # MIDI pitches


def make_wav(path, bpm=100):
    import numpy as np, soundfile as sf
    sr, eighth = 44100, 60 / bpm / 2
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    audio = np.zeros(int(sr * (len(LINE) * eighth + 1)))
    for i, m in enumerate(LINE):
        n = int(sr * eighth * 0.95)
        t = np.arange(n) / sr
        env = np.exp(-t * 4) * np.minimum(1, t * 400)
        sig = sum(a * np.sin(2 * np.pi * f(m) * h * t)
                  for h, a in [(1, 1), (2, .5), (3, .28), (4, .15)]) * env
        s = int(i * eighth * sr)
        audio[s:s + n] += sig
    sf.write(path, audio / np.abs(audio).max() / 1.2, sr)


def main():
    try:
        import torch
        dev = "cuda (GPU)" if torch.cuda.is_available() else "cpu (slower, still fine)"
        print(f"[selftest] torch {torch.__version__} -> demucs will use {dev}")
    except Exception as e:
        print(f"[selftest] WARNING: torch import failed ({e}); demucs will not work")
    tmp = tempfile.mkdtemp(prefix="basstab-selftest-")
    wav = os.path.join(tmp, "selftest_bass.wav")
    make_wav(wav)
    env = dict(os.environ, BASSENV=sys.prefix, BASSTAB_ROOT=tmp)
    r = subprocess.run(["bash", os.path.join(HERE, "basstab.sh"), "--input", wav,
                        "--no-separate", "--bpm", "100", "--grid", "8", "--slug", "selftest"],
                       env=env, capture_output=True, text=True)
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT ")), None)
    if not line:
        print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
        sys.exit("[selftest] FAILED: no RESULT line")
    res = json.loads(line[len("RESULT "):])
    if not res.get("ok"):
        sys.exit(f"[selftest] FAILED: {res.get('error')} (log: {res.get('log')})")
    notes = int(re.search(r"notes=(\d+)", res["summary"]).group(1))
    print(open(res["tab"]).read())
    png = os.path.join(res["out_dir"], "selftest.tab.png")
    if not (os.path.exists(png) and os.path.getsize(png) > 10000):
        sys.exit(f"[selftest] FAILED: no typeset tab at {png}")
    if not 12 <= notes <= 20:
        sys.exit(f"[selftest] FAILED: expected ~16 notes, got {notes}")
    print(f"[selftest] PASS - {notes} notes detected (ground truth 16); "
          f"outputs in {res['out_dir']}")


if __name__ == "__main__":
    main()
