#!/usr/bin/env python3
"""midi_to_basstab.py - basic-pitch MIDI -> playable ASCII bass tab."""
import argparse, math, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import pretty_midi
from fretboard import TUNINGS, PITCH_CLASSES as NAMES, resolve, string_name

HARMONIC_INTERVALS = {12, 19, 24, 28, 31}

def pname(p):
    return f"{NAMES[p % 12]}{p // 12 - 1}"

def load_notes(path, vel_floor_ratio):
    pm = pretty_midi.PrettyMIDI(path)
    notes = sorted((n for i in pm.instruments if not i.is_drum for n in i.notes),
                   key=lambda n: (n.start, n.pitch))
    if not notes:
        sys.exit("no notes in MIDI")
    vels = sorted(n.velocity for n in notes)
    floor = vels[len(vels) // 2] * vel_floor_ratio
    kept = [n for n in notes if n.velocity >= floor]
    return kept, len(notes) - len(kept)

def suppress_harmonics(notes):
    drop = set()
    for i, a in enumerate(notes):
        if i in drop:
            continue
        for j in range(i + 1, len(notes)):
            b = notes[j]
            if b.start > a.end:
                break
            if j in drop:
                continue
            iv = b.pitch - a.pitch
            if any(abs(iv - h) <= 1 for h in HARMONIC_INTERVALS) \
               and b.start >= a.start - 0.03 and b.velocity <= a.velocity * 1.35:
                drop.add(j)
    return [n for i, n in enumerate(notes) if i not in drop], len(drop)

def _bpm_from_iois(notes):
    iois = [b.start - a.start for a, b in zip(notes, notes[1:]) if 0.06 < b.start - a.start < 2]
    if not iois:
        return 120.0, "default"
    iois.sort()
    bpm = 60.0 / iois[len(iois) // 2] / 2
    while bpm < 65: bpm *= 2
    while bpm > 190: bpm /= 2
    return bpm, "ioi-estimate"


def detect_tempo(args, notes):
    """Return (bpm, source, offset, beat_lock).

    `offset` is the time of the bar line bar 1 starts on. Tempo comes from the
    waveform when audio is available (tempo.py: spectral-flux onset envelope +
    autocorrelation); the bar phase comes from the notes instead, because a
    grid fitted to the waveform locks to the beat and not to the bar. The
    result is walked back whole bars to sit at or before the first note, so a
    pickup is not quantized to a negative slot and dropped.
    """
    onsets = [n.start for n in notes]
    bpm = float(args.bpm) if args.bpm else None
    source = "user" if bpm else None
    lock = None

    if args.audio:
        try:
            from tempo import analyse_audio
            got = analyse_audio(args.audio, bpm=bpm)
            lock = got["beat_lock"]
            if bpm is None:
                bpm, source = got["bpm"], "onset-envelope"
        except Exception as e:
            print(f"[warn] audio tempo analysis failed ({e}); using note onsets",
                  file=sys.stderr)

    if bpm is None:
        bpm, source = _bpm_from_iois(notes)

    if args.offset is not None:
        return bpm, source, float(args.offset), lock
    if not onsets:
        return bpm, source, 0.0, lock

    try:
        from rhythm import downbeat_from_notes
        down, _ = downbeat_from_notes(
            [(n.start, n.end, n.pitch, n.velocity) for n in notes],
            bpm, args.meter, max(1, args.grid // 4))
    except Exception as e:
        print(f"[warn] downbeat search failed ({e}); bar 1 starts at t=0",
              file=sys.stderr)
        return bpm, source, 0.0, lock

    # step whole bars back so the first note is not quantized to a negative slot
    bar = 60.0 / bpm * args.meter
    down += bar * math.floor((min(onsets) - down) / bar)
    return bpm, source, down, lock


def register_report(raw, tuning, frets):
    """Where the line sits relative to what the tuning can actually reach."""
    lo, hi = min(tuning), max(tuning) + frets
    return {"below": sum(1 for p in raw if p < lo),
            "above": sum(1 for p in raw if p > hi),
            "median": sorted(raw)[len(raw) // 2]}


def tuning_hint(raw, tuning):
    """Suggest a lower tuning when notes keep falling under the lowest string."""
    lo = min(tuning)
    below = [p for p in raw if p < lo]
    if len(below) < max(3, 0.03 * len(raw)):
        return None
    deepest = min(below)
    for name in ("EbAbDbGb", "DADG", "BEADG"):    # least exotic that reaches it
        if min(TUNINGS[name]) <= deepest and min(TUNINGS[name]) < lo:
            return name, len(below), deepest
    return None

def quantize(notes, bpm, grid, offset):
    slot = 60.0 / bpm / (grid / 4)
    out = {}
    for n in notes:
        s = round((n.start - offset) / slot)
        if s < 0: continue
        out.setdefault(s, []).append((n, max(1, round((n.end - n.start) / slot))))
    events = []
    for s in sorted(out):
        vmax = max(n.velocity for n, _ in out[s])
        loud = [(n, d) for n, d in out[s] if n.velocity >= 0.45 * vmax]
        n, d = min(loud, key=lambda x: (x[0].pitch, -x[1]))
        events.append([s, n.pitch, d, n.velocity])
    for a, b in zip(events, events[1:]):
        a[2] = min(a[2], b[0] - a[0])
    return events, slot

def fold_to_range(events, tuning, frets):
    lo, hi = tuning[0], tuning[-1] + frets
    folds = 0
    for e in events:
        while e[1] < lo: e[1] += 12; folds += 1
        while e[1] > hi: e[1] -= 12; folds += 1
    return folds

def map_frets(events, tuning, frets):
    def cands(p):
        return [(s, p - o) for s, o in enumerate(tuning) if 0 <= p - o <= frets]
    prev = None
    for e in events:
        cur = []
        for s, f in cands(e[1]):
            base = 0.12 * f
            if prev is None:
                cur.append((base, (s, f), None))
            else:
                best = min((pc + base + (0.3 * f if pf == 0 or f == 0 else abs(f - pf))
                            + 0.4 * abs(s - ps), k) for k, (pc, (ps, pf), _) in enumerate(prev))
                cur.append((best[0], (s, f), best[1]))
        e.append(cur); prev = cur
    if not events: return
    k = min(range(len(events[-1][4])), key=lambda i: events[-1][4][i][0])
    for e in reversed(events):
        cost, (s, f), back = e[4][k]
        e[4] = (s, f)
        k = back if back is not None else 0

def render(events, tuning, grid, meter, bars_per_line, bpm, title):
    slots_bar = grid * meter // 4
    labels = [string_name(t) for t in tuning]
    w = max(len(x) for x in labels)
    total_bars = (max(e[0] for e in events) // slots_bar) + 1 if events else 0
    grid_map = {e[0]: e for e in events}
    lines_out = [f"# {title}", f"# BPM {bpm:.1f} | {meter}/4 | grid 1/{grid} | tuning "
                 + " ".join(pname(t) for t in tuning), ""]
    for line_start in range(0, total_bars, bars_per_line):
        rows = {s: [] for s in range(len(tuning))}
        for b in range(line_start, min(line_start + bars_per_line, total_bars)):
            for s in rows: rows[s].append("|")
            for slot in range(b * slots_bar, (b + 1) * slots_bar):
                e = grid_map.get(slot)
                width = (len(str(e[4][1])) if e else 1) + 1
                for s in rows:
                    rows[s].append(str(e[4][1]).ljust(width, "-") if e and e[4][0] == s else "-" * width)
        for s in rows: rows[s].append("|")
        lines_out.append(f"  bar {line_start + 1}")
        for s in reversed(range(len(tuning))):
            lines_out.append(labels[s].rjust(w) + "".join(rows[s]))
        lines_out.append("")
    return "\n".join(lines_out)

def write_midi(events, slot_dur, path):
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=33, name="bass (cleaned)")
    for e in events:
        inst.notes.append(pretty_midi.Note(velocity=int(e[3]), pitch=e[1],
                          start=e[0] * slot_dur, end=(e[0] + e[2]) * slot_dur))
    pm.instruments.append(inst); pm.write(path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("midi"); ap.add_argument("-o", "--out")
    ap.add_argument("--bpm", type=float); ap.add_argument("--audio")
    ap.add_argument("--tuning", default="EADG"); ap.add_argument("--frets", type=int, default=20)
    ap.add_argument("--grid", type=int, default=16); ap.add_argument("--meter", type=int, default=4)
    ap.add_argument("--bars-per-line", type=int, default=4)
    ap.add_argument("--offset", type=float, default=None,
                    help="bar-1 time in seconds; default: detect the downbeat")
    ap.add_argument("--png", help="also write a typeset tab image here")
    ap.add_argument("--transpose", type=int, default=0); ap.add_argument("--vel-floor", type=float, default=0.35)
    ap.add_argument("--no-harmonic-filter", action="store_true"); ap.add_argument("--midi-out")
    ap.add_argument("--title", default="bass tab")
    a = ap.parse_args()
    tuning = resolve(a.tuning)
    notes, n_vel = load_notes(a.midi, a.vel_floor)
    for n in notes: n.pitch += a.transpose
    n_harm = 0
    if not a.no_harmonic_filter: notes, n_harm = suppress_harmonics(notes)
    bpm, src, offset, lock = detect_tempo(a, notes)
    events, slot_dur = quantize(notes, bpm, a.grid, offset)
    if not events:
        sys.exit("every note quantized away - check --bpm and --offset")
    raw = [e[1] for e in events]                 # pitches before octave folding
    reg = register_report(raw, tuning, a.frets)
    hint = tuning_hint(raw, tuning)
    folds = fold_to_range(events, tuning, a.frets)
    map_frets(events, tuning, a.frets)
    tab = render(events, tuning, a.grid, a.meter, a.bars_per_line, bpm, a.title)
    if a.out: open(a.out, "w").write(tab + "\n")
    else: print(tab)
    if a.midi_out: write_midi(events, slot_dur, a.midi_out)
    if a.png:
        from render_tab import render_png
        div = max(1, a.grid // 4)
        render_png([(e[0], e[4]) for e in events], a.png,
                   title=a.title,
                   subtitle=f"BPM {bpm:.1f} ({src})  |  {a.meter}/4  |  grid 1/{a.grid}",
                   tuning=tuning, div=div, bpb=a.meter,
                   bars_per_line=a.bars_per_line)

    lockbit = f" lock={lock:.2f}" if lock is not None else ""
    print(f"[summary] notes={len(events)} bpm={bpm:.1f}({src}) bar1={offset:.2f}s{lockbit} "
          f"dropped: vel_floor={n_vel} harmonics={n_harm} | octave_folds={folds} | range "
          f"{pname(min(e[1] for e in events))}-{pname(max(e[1] for e in events))}"
          + (f" | tab -> {a.out}" if a.out else "")
          + (f" | png -> {a.png}" if a.png else ""), file=sys.stderr)
    # Octave errors are the standard failure on bass, but "folded" on its own does
    # not say which way: below the low string usually means the wrong tuning,
    # above the top fret or a high centre of mass means a synth-bass octave error.
    if hint:
        name, n, deepest = hint
        print(f"[warn] {n} notes fall below the lowest open string ({pname(deepest)}) - "
              f"the song may be in {name}; try --tuning {name}", file=sys.stderr)
    if reg["above"] > len(raw) * 0.05:
        print(f"[warn] {reg['above']} notes sit past fret {a.frets} and were folded down - "
              f"try --frets 24, or --transpose -12 if the line is an octave high",
              file=sys.stderr)
    if reg["median"] > min(tuning) + 24:
        print(f"[warn] the line centres on {pname(reg['median'])}, high for a bass - "
              "synth-bass octave error likely; try --transpose -12", file=sys.stderr)
    if folds > len(events) * 0.15 and not hint and not reg["above"]:
        print(f"[warn] {folds} notes were octave-folded to fit the fretboard - "
              "check the tuning and the register", file=sys.stderr)

if __name__ == "__main__":
    main()
