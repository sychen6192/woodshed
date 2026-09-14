"""Tempo estimation + grid quantization for note events."""
import numpy as np


def estimate_bpm(events, lo=60.0, hi=200.0):
    """Estimate tempo from onset times via IOI comb-filter scoring."""
    onsets = np.array([e["start"] for e in events])
    if len(onsets) < 8:
        return None, 0.0

    iois = np.diff(onsets)
    iois = iois[(iois > 0.08) & (iois < 2.0)]
    if len(iois) < 4:
        return None, 0.0

    best, best_score = None, -1.0
    # score each candidate tempo by how well IOIs land on its subdivisions
    for bpm in np.arange(lo, hi, 0.25):
        beat = 60.0 / bpm
        # allow whole, half, quarter, and dotted subdivisions of the beat
        ratios = iois / beat
        err = np.abs(ratios - np.round(ratios * 4) / 4)
        score = float(np.sum(np.exp(-(err ** 2) / (2 * 0.04 ** 2))))
        if score > best_score:
            best_score, best = score, bpm

    conf = best_score / len(iois)
    return float(best), float(conf)


def find_downbeat(events, bpm, beats_per_bar=4):
    """Pick the phase offset whose bar lines catch the most onsets."""
    onsets = np.array([e["start"] for e in events])
    bar = 60.0 / bpm * beats_per_bar
    best, best_score = 0.0, -1.0
    for phase in np.linspace(0, bar, 64, endpoint=False):
        d = np.abs(((onsets - phase) % bar))
        d = np.minimum(d, bar - d)
        score = float(np.sum(np.exp(-(d ** 2) / (2 * 0.06 ** 2))))
        if score > best_score:
            best_score, best = score, phase
    return float(best)


def quantize(events, bpm, downbeat, div=4, beats_per_bar=4):
    """Snap onsets to a grid of `div` subdivisions per beat.

    Returns list of dicts with an added integer 'slot' (grid index from
    the downbeat) and 'bar' / 'pos' decomposition.
    """
    step = 60.0 / bpm / div
    slots_per_bar = div * beats_per_bar
    out = []
    seen = set()
    for e in events:
        slot = int(round((e["start"] - downbeat) / step))
        if slot < 0:
            continue
        if slot in seen:          # collapse duplicates landing on one slot
            continue
        seen.add(slot)
        out.append({**e,
                    "slot": slot,
                    "bar": slot // slots_per_bar,
                    "pos": slot % slots_per_bar})
    return out


def analyse(events, div=4, beats_per_bar=4):
    bpm, conf = estimate_bpm(events)
    if bpm is None:
        return None
    db = find_downbeat(events, bpm, beats_per_bar)
    q = quantize(events, bpm, db, div, beats_per_bar)
    return {"bpm": bpm, "confidence": conf, "downbeat": db,
            "div": div, "beats_per_bar": beats_per_bar, "notes": q}



def downbeat_from_notes(notes, bpm, beats_per_bar=4, subdiv=4):
    """Find the bar phase that best explains where the line puts its weight.

    A beat grid fitted to a waveform locks to the beat but not to the bar, and
    on a steady stream of eighths it will happily lock to an offbeat. Note data
    breaks the tie: a bass line lands the root on beat 1, holds it longer and
    hits it harder. Score every candidate phase by that weighted onset mass.

    notes: [(start, end, pitch, velocity)]. Returns (phase_seconds, score).
    """
    if not notes:
        return 0.0, 0.0
    starts = np.array([n[0] for n in notes], dtype=float)
    durs = np.array([n[1] - n[0] for n in notes], dtype=float)
    pitches = np.array([n[2] for n in notes], dtype=float)
    vels = np.array([n[3] for n in notes], dtype=float)

    beat = 60.0 / bpm
    bar = beat * beats_per_bar
    sigma = beat / subdiv / 2                     # half a subdivision

    accent = vels / max(vels.max(), 1.0)
    held = np.minimum(durs / beat, 1.0)
    span = pitches.max() - pitches.min()
    low = (pitches.max() - pitches) / span if span > 0 else np.ones_like(pitches)
    weight = accent * (1.0 + held) * (1.0 + low)

    best, best_score = 0.0, -1.0
    for phase in np.linspace(0, bar, beats_per_bar * subdiv * 4, endpoint=False):
        off = (starts - phase) % bar
        dist = np.minimum(off, bar - off)
        score = float(np.sum(weight * np.exp(-(dist ** 2) / (2 * sigma ** 2))))
        if score > best_score:
            best_score, best = score, float(phase)
    return best, best_score
