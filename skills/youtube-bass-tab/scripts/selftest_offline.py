#!/usr/bin/env python3
"""selftest_offline.py - check everything downstream of the transcription engine.

selftest.py exercises the whole pipeline and therefore needs demucs, basic-pitch
and torch. This one needs only numpy, scipy, soundfile, matplotlib and
pretty_midi, so it runs anywhere and covers the parts that are ours: tempo,
downbeat, quantization, the fret solver, both renderers, and the register
warnings. It builds its own audio and MIDI with a known answer.

    python scripts/selftest_offline.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))

BPM = 100.0
BEAT = 60.0 / BPM                 # 0.6 s
EIGHTH = BEAT / 2
BAR = BEAT * 4                    # 2.4 s
DOWNBEAT = 0.85                   # deliberately not t=0
BARS = 8
LINE = [28, 31, 33, 35, 36, 35, 33, 31]     # E1 walk-up, one bar of eighths

FAILURES = []


def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not ok:
        FAILURES.append(name)


def build(tmp):
    """Write a wav and a MIDI of the same line. Returns (wav, mid, n_notes)."""
    import numpy as np
    import soundfile as sf
    import pretty_midi

    notes = [(DOWNBEAT - EIGHTH, 31, 70)]            # a pickup, before bar 1
    for b in range(BARS):
        for i, p in enumerate(LINE):
            notes.append((DOWNBEAT + b * BAR + i * EIGHTH, p, 110 if i == 0 else 80))

    sr = 44100
    audio = np.zeros(int(sr * (DOWNBEAT + BARS * BAR + 1.0)), dtype=np.float32)
    for t, p, vel in notes:
        f = 440.0 * 2 ** ((p - 69) / 12)
        n = int(sr * EIGHTH * 0.9)
        tt = np.arange(n) / sr
        env = np.exp(-tt * 5) * np.minimum(1, tt * 600)
        sig = sum(a * np.sin(2 * np.pi * f * h * tt)
                  for h, a in [(1, 1.0), (2, .5), (3, .28), (4, .15)]) * env * (vel / 110)
        s = int(t * sr)
        audio[s:s + n] += sig.astype(np.float32)
    wav = os.path.join(tmp, "line.wav")
    sf.write(wav, audio / (np.abs(audio).max() * 1.15), sr)

    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=33)
    for t, p, vel in notes:
        inst.notes.append(pretty_midi.Note(velocity=vel, pitch=p,
                                           start=t, end=t + EIGHTH * 0.9))
    pm.instruments.append(inst)
    mid = os.path.join(tmp, "line.mid")
    pm.write(mid)
    return wav, mid, len(notes)


def write_midi(path, pitches, vel=90):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=33)
    for i, p in enumerate(pitches):
        inst.notes.append(pretty_midi.Note(velocity=vel, pitch=p,
                                           start=i * EIGHTH, end=i * EIGHTH + EIGHTH * .9))
    pm.instruments.append(inst)
    pm.write(path)


def run_tab(args):
    """Run midi_to_basstab.py, returning its stderr (summary + warnings)."""
    r = subprocess.run([sys.executable, os.path.join(HERE, "midi_to_basstab.py")] + args,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return f"[exit {r.returncode}] {r.stderr}"
    return r.stderr


def main():
    tmp = tempfile.mkdtemp(prefix="basstab-offline-")
    print(f"[selftest-offline] workdir {tmp}")

    # --- fret solver and tuning table ---------------------------------------
    print("\nfretboard")
    from fretboard import TUNINGS, resolve, solve, render, string_name
    check("alias table agrees",
          TUNINGS["EADG"] == TUNINGS["standard4"]
          and TUNINGS["BEADG"] == TUNINGS["standard5"]
          and TUNINGS["DADG"] == TUNINGS["drop_d4"]
          and resolve("28,33,38,43") == [28, 33, 38, 43])
    check("string names cover half-step-down tuning",
          [string_name(t) for t in resolve("EbAbDbGb")] == ["Eb", "Ab", "Db", "Gb"])
    pos = solve([40, 42, 43, 45, 47, 48, 50, 52], "standard4")
    check("solver stays in position", max(f for _, f in pos) - min(f for _, f in pos) <= 9,
          f"frets {sorted({f for _, f in pos})}")
    check("renders every string", render(pos, "standard5").count("\n") >= 5)

    # --- tempo and downbeat on real audio -----------------------------------
    print("\ntempo + downbeat")
    wav, mid, n_notes = build(tmp)
    from tempo import analyse_audio
    got = analyse_audio(wav)
    check("bpm from onset envelope", abs(got["bpm"] - BPM) < 1.5,
          f"{got['bpm']:.2f} vs {BPM}")

    from rhythm import downbeat_from_notes
    import pretty_midi
    notes = pretty_midi.PrettyMIDI(mid).instruments[0].notes
    phase, _ = downbeat_from_notes([(n.start, n.end, n.pitch, n.velocity) for n in notes],
                                   BPM, 4, 4)
    err = min(abs(phase - DOWNBEAT), BAR - abs(phase - DOWNBEAT))
    check("downbeat found from note weight", err < 0.06, f"{phase:.3f}s vs {DOWNBEAT}s")

    # --- end to end through the renderer ------------------------------------
    print("\nrenderer")
    tab = os.path.join(tmp, "out.tab")
    png = os.path.join(tmp, "out.png")
    err_txt = run_tab([mid, "--audio", wav, "--grid", "16", "-o", tab, "--png", png])
    summary = next((l for l in err_txt.splitlines() if l.startswith("[summary]")), "")
    check("summary emitted", bool(summary), summary[:90])
    check("every note survived", f"notes={n_notes} " in summary)
    # bar 1 is stepped back a whole bar so the pickup keeps a positive slot
    check("bar 1 lands on the downbeat", " bar1=-1.5" in summary)
    check("png written", os.path.exists(png) and os.path.getsize(png) > 10000)
    # 16 slots x 2 chars; the pickup is one eighth before bar 2, i.e. slot 14
    bar1 = next(l for l in open(tab) if l.startswith("E|")).split("|")[1]
    check("pickup alone at slot 14 of bar 1", bar1 == "-" * 28 + "3" + "-" * 3,
          repr(bar1))
    check("no spurious warnings on a clean line", "[warn]" not in err_txt)

    # --- register and tuning warnings ---------------------------------------
    print("\nregister warnings")
    base = LINE * 4
    cases = [
        ("drop D pedal", [26 if i % 4 == 0 else p for i, p in enumerate(base)], "--tuning DADG"),
        ("half step down", [p - 1 for p in base], "--tuning EbAbDbGb"),
        ("low B pedal", [23 if i % 4 == 0 else p for i, p in enumerate(base)], "--tuning BEADG"),
        ("synth bass 2 octaves up", [p + 24 for p in base], "--transpose -12"),
    ]
    for name, pitches, expect in cases:
        f = os.path.join(tmp, name.replace(" ", "_") + ".mid")
        write_midi(f, pitches)
        out = run_tab([f, "--bpm", str(BPM), "-o", os.devnull])
        warns = [l for l in out.splitlines() if l.startswith("[warn]")]
        check(f"{name} -> {expect}",
              len(warns) == 1 and expect in warns[0],
              warns[0][7:80] if warns else "no warning")

    # --- crepe events reach the same renderer -------------------------------
    print("\ncrepe engine glue")
    from crepe_to_midi import events_to_midi
    ev = [{"start": DOWNBEAT + i * EIGHTH, "end": DOWNBEAT + i * EIGHTH + EIGHTH * .9,
           "pitch": p, "amp": 0.9 if i % 8 == 0 else 0.7}
          for i, p in enumerate(LINE * BARS)]
    cmid = os.path.join(tmp, "crepe.mid")
    n = events_to_midi(ev, cmid)
    check("crepe events -> midi", n == len(ev), f"{n} notes")
    out = run_tab([cmid, "--audio", wav, "-o", os.devnull])
    check("crepe midi renders", "[summary]" in out and f"notes={len(ev)} " in out)

    print()
    if FAILURES:
        sys.exit(f"[selftest-offline] FAILED: {', '.join(FAILURES)}")
    print("[selftest-offline] PASS")


if __name__ == "__main__":
    main()
