#!/usr/bin/env python3
"""crepe_to_midi.py - torchcrepe bass transcription -> MIDI.

Emits the same shape basic-pitch does, so one tab renderer serves both engines.
The two differ in what they can tell you: basic-pitch is polyphonic and reports
a velocity per note, torchcrepe is monophonic and reports a periodicity
confidence per frame. The renderer's velocity floor and harmonic filter need
something in the velocity slot, so confidence is mapped onto it.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pretty_midi

VEL_FLOOR, VEL_SPAN = 40, 87       # confidence 0..1 -> MIDI velocity 40..127


def events_to_midi(events, path, program=33):
    """events: [{start, end, pitch, amp}], amp in 0..1. Returns note count."""
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=program, name="bass (crepe)")
    for e in events:
        conf = max(0.0, min(1.0, float(e.get("amp", 0.8))))
        inst.notes.append(pretty_midi.Note(
            velocity=int(round(VEL_FLOOR + VEL_SPAN * conf)),
            pitch=int(e["pitch"]), start=float(e["start"]), end=float(e["end"])))
    pm.instruments.append(inst)
    pm.write(path)
    return len(inst.notes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("out")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--conf", type=float, default=0.55,
                    help="crepe periodicity threshold; raise if noisy")
    a = ap.parse_args()

    from pitch import transcribe
    events = transcribe(a.wav, device=a.device, conf_threshold=a.conf)
    if not events:
        sys.exit("crepe found no notes - check the stem audio")
    print(f"[crepe] {events_to_midi(events, a.out)} notes -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
