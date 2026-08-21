"""Fretboard solver: MIDI note sequence -> bass tab via Viterbi DP."""

TUNINGS = {
    "standard4": [28, 33, 38, 43],       # E1 A1 D2 G2
    "drop_d4":   [26, 33, 38, 43],
    "standard5": [23, 28, 33, 38, 43],   # B0 added
}

MAX_FRET = 24
OPEN_STRING_BONUS = 1.5   # open strings are cheap to play
PREFERRED_FRET = 5.0      # neutral hand position
POS_SHIFT_W = 2.0         # penalty per fret of hand movement
STRING_SKIP_W = 2.5       # penalty per string crossed


def candidates(note, tuning):
    """All playable (string_index, fret) pairs for a MIDI note."""
    out = []
    for s, open_note in enumerate(tuning):
        fret = note - open_note
        if 0 <= fret <= MAX_FRET:
            out.append((s, fret))
    return out


def transition_cost(prev, cur):
    """Cost of moving the fretting hand from prev position to cur."""
    s0, f0 = prev
    s1, f1 = cur
    c = 0.0
    if f1 > 0 and f0 > 0:
        c += abs(f1 - f0) * POS_SHIFT_W
    c += abs(s1 - s0) * STRING_SKIP_W
    # open-string bonus only when it does not force a wide string jump
    if f1 == 0 and abs(s1 - s0) <= 1:
        c -= OPEN_STRING_BONUS
    if f1 > 12:
        c += (f1 - 12) * 0.3      # upper register is awkward on bass
    return c


def fold_into_range(notes, tuning):
    """Octave-shift out-of-range notes back into playable territory.

    CREPE produces sub-harmonic octave errors on bass material, yielding
    notes below the lowest open string. Transposing by whole octaves keeps
    pitch class intact, which is what matters for a tab.
    """
    lo, hi = min(tuning), max(tuning) + MAX_FRET
    out = []
    for n in notes:
        while n < lo:
            n += 12
        while n > hi:
            n -= 12
        out.append(n)
    return out


def solve(notes, tuning_name="standard4"):
    """Viterbi over fretboard positions. Returns list of (string, fret)."""
    tuning = TUNINGS[tuning_name]
    if not notes:
        return []
    notes = fold_into_range(notes, tuning)

    # init
    paths = {}
    for cand in candidates(notes[0], tuning):
        cost = abs(cand[1] - PREFERRED_FRET) - (OPEN_STRING_BONUS if cand[1] == 0 else 0)
        paths[cand] = (cost, [cand])
    if not paths:
        raise ValueError(f"note {notes[0]} out of range for {tuning_name}")

    for note in notes[1:]:
        cands = candidates(note, tuning)
        if not cands:
            continue  # skip unplayable note rather than abort
        nxt = {}
        for cand in cands:
            best = min(
                ((c + transition_cost(prev, cand), p) for prev, (c, p) in paths.items()),
                key=lambda x: x[0],
            )
            nxt[cand] = (best[0], best[1] + [cand])
        paths = nxt

    return min(paths.values(), key=lambda x: x[0])[1]


def render(positions, tuning_name="standard4", per_line=48, labels=None):
    """ASCII tab. labels: optional per-note strings (e.g. rhythm marks)."""
    tuning = TUNINGS[tuning_name]
    names = {28: "E", 33: "A", 38: "D", 43: "G", 26: "D", 23: "B"}
    n_str = len(tuning)

    cols = []
    for i, (s, f) in enumerate(positions):
        txt = str(f)
        lab = labels[i] if labels else ""
        w = max(len(txt), len(lab)) + 1
        col = ["-" * w for _ in range(n_str)]
        col[s] = txt.ljust(w, "-")
        cols.append((col, lab.ljust(w)))

    out = []
    for start in range(0, len(cols), per_line):
        chunk = cols[start:start + per_line]
        if labels:
            out.append("   " + "".join(c[1] for c in chunk))
        # high string printed on top
        for si in reversed(range(n_str)):
            name = names.get(tuning[si], "?")
            out.append(f"{name}|" + "".join(c[0][si] for c in chunk) + "|")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    # sanity check: chromatic run + an octave leap
    seq = [40, 42, 43, 45, 47, 48, 50, 52, 40, 52]
    pos = solve(seq)
    print(render(pos))
    print("positions:", pos)
