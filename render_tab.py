"""Render note events as a typeset bass tab PNG."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from fretboard import solve, TUNINGS

STR_NAMES = {28: "E", 33: "A", 38: "D", 43: "G", 26: "D", 23: "B"}

BG = "#faf8f4"
INK = "#1c1c1c"
LINE = "#9a9285"
BAR = "#5c564c"
ACCENT = "#b5462f"
GRID = "#e2ddd2"


def build_grid(events, bpm, phase, div=4, bpb=4, tuning="standard4",
               trim_lead=True):
    """Map events onto integer grid slots and solve fretboard positions."""
    step = 60.0 / bpm / div
    slots = []
    for e in events:
        s = int(round((e["start"] - phase) / step))
        slots.append(max(0, s))

    # dedupe: one note per slot (keep highest confidence)
    best = {}
    for e, s in zip(events, slots):
        if s not in best or e["amp"] > best[s]["amp"]:
            best[s] = e
    ordered = sorted(best.items())

    if trim_lead and ordered:
        # drop empty lead-in bars so bar 1 contains the first note
        spb = div * bpb
        shift = (ordered[0][0] // spb) * spb
        ordered = [(s - shift, e) for s, e in ordered]

    pitches = [e["pitch"] for _, e in ordered]
    pos = solve(pitches, tuning)
    return [(s, p) for (s, _), p in zip(ordered, pos)]


def render_png(placed, out, title="", subtitle="", tuning="standard4",
               div=4, bpb=4, bars_per_line=4, dpi=150):
    tun = TUNINGS[tuning]
    n_str = len(tun)
    spb = div * bpb                      # slots per bar
    spl = spb * bars_per_line            # slots per line

    max_slot = max(s for s, _ in placed)
    n_lines = max_slot // spl + 1

    row_h = 1.0
    line_h = n_str * 0.42 + 1.05
    fig_w = 13.0
    head_h = 1.9 if title else 0.6
    fig_h = head_h + n_lines * line_h

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    x0, x1 = 0.055, 0.975
    span = x1 - x0

    def sx(slot_in_line):
        return x0 + span * (slot_in_line / spl)

    top = 1.0 - (head_h - 0.55) / fig_h

    for li in range(n_lines):
        base = top - li * (line_h / fig_h)
        str_gap = 0.40 / fig_h

        ys = [base - i * str_gap for i in range(n_str)]

        # subdivision grid
        for b in range(bars_per_line):
            for d in range(bpb):
                gx = sx(b * spb + d * div)
                ax.plot([gx, gx], [ys[-1], ys[0]], color=GRID,
                        lw=0.6, zorder=1)

        # string lines
        for i, y in enumerate(ys):
            ax.plot([x0, x1], [y, y], color=LINE, lw=0.9, zorder=2)
            ax.text(x0 - 0.016, y, STR_NAMES.get(tun[n_str - 1 - i], "?"),
                    ha="right", va="center", fontsize=10.5,
                    color=BAR, family="DejaVu Sans", weight="bold", zorder=3)

        # bar lines
        for b in range(bars_per_line + 1):
            bx = sx(b * spb)
            ax.plot([bx, bx], [ys[-1], ys[0]], color=BAR, lw=1.6, zorder=4)

        # bar numbers (offset in figure-relative units, independent of scale)
        num_dy = 0.24 / fig_h
        for b in range(bars_per_line):
            num = li * bars_per_line + b + 1
            ax.text(sx(b * spb) + 0.004, ys[0] + num_dy,
                    str(num), ha="left", va="bottom", fontsize=7.5,
                    color="#8d8578", family="DejaVu Sans", zorder=5)

        # notes
        lo, hi = li * spl, (li + 1) * spl
        for slot, (si, fret) in placed:
            if not (lo <= slot < hi):
                continue
            y = ys[n_str - 1 - si]
            x = sx(slot - lo)
            txt = str(fret)
            w = 0.0115 + 0.0075 * (len(txt) - 1)
            ax.add_patch(Rectangle((x - w, y - 0.0088 * 14 / fig_h * 1.0),
                                   2 * w, 0.0176 * 14 / fig_h,
                                   facecolor=BG, edgecolor="none", zorder=6))
            ax.text(x, y, txt, ha="center", va="center", fontsize=9.5,
                    color=ACCENT if fret == 0 else INK,
                    family="DejaVu Sans", weight="bold", zorder=7)

    if title:
        ax.text(0.5, 1.0 - 0.30 / fig_h, title, ha="center", va="top",
                fontsize=17, color=INK, family="DejaVu Sans", weight="bold")
    if subtitle:
        ax.text(0.5, 1.0 - 0.72 / fig_h, subtitle, ha="center", va="top",
                fontsize=9.5, color="#7d7568", family="DejaVu Sans")

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.savefig(out, dpi=dpi, facecolor=BG, bbox_inches="tight",
                pad_inches=0.22)
    plt.close(fig)
    return out
