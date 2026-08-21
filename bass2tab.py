#!/usr/bin/env python3
"""bass2tab: audio (file or YouTube URL) -> isolated bass -> MIDI -> ASCII tab."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from fretboard import solve, render, TUNINGS


def fetch(src, workdir):
    """Return a wav path. src may be a local file or a URL."""
    out = workdir / "input.wav"
    if src.startswith(("http://", "https://")):
        subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "wav", "--audio-quality", "0",
             "-o", str(workdir / "input.%(ext)s"), src],
            check=True,
        )
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-ac", "2", "-ar", "44100", str(out)],
            check=True, capture_output=True,
        )
    if not out.exists():
        raise FileNotFoundError("no wav produced")
    return out


def isolate_bass(wav, workdir, device="cuda"):
    """Demucs two-stem separation. Returns path to the bass-only wav."""
    subprocess.run(
        [sys.executable, "-m", "demucs", "-n", "htdemucs", "--two-stems", "bass",
         "-d", device, "-o", str(workdir / "sep"), str(wav)],
        check=True,
    )
    hits = list((workdir / "sep").rglob("bass.wav"))
    if not hits:
        raise FileNotFoundError("demucs produced no bass stem")
    return hits[0]


def transcribe(wav, device="cuda", conf=0.55):
    """torchcrepe pitch tracking -> monophonic note events."""
    from pitch import transcribe as _t
    return _t(wav, device=device, conf_threshold=conf)


def rhythm_labels(events, bpm):
    """Map inter-onset intervals to coarse rhythm symbols."""
    if not bpm:
        return None
    beat = 60.0 / bpm
    sym = [(4, "w"), (2, "h"), (1, "q"), (0.5, "e"), (0.25, "s")]
    labs = []
    for i, e in enumerate(events):
        dur = (events[i + 1]["start"] - e["start"]) if i + 1 < len(events) \
            else (e["end"] - e["start"])
        beats = dur / beat
        labs.append(min(sym, key=lambda s: abs(s[0] - beats))[1])
    return labs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="audio file path or URL")
    ap.add_argument("-t", "--tuning", default="standard4", choices=TUNINGS)
    ap.add_argument("--bpm", type=float, default=None, help="enable rhythm row")
    ap.add_argument("--skip-demucs", action="store_true",
                    help="input is already an isolated bass track")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--conf", type=float, default=0.55,
                    help="crepe periodicity threshold; raise if noisy")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        wav = fetch(args.source, wd)
        print(f"[1/4] audio ready: {wav.name}", file=sys.stderr)

        stem = wav if args.skip_demucs else isolate_bass(wav, wd, args.device)
        print(f"[2/4] bass stem: {stem.name}", file=sys.stderr)

        events = transcribe(stem, args.device, args.conf)
        print(f"[3/4] {len(events)} notes detected", file=sys.stderr)
        if not events:
            sys.exit("no notes detected -- check the stem audio")

        pitches = [e["pitch"] for e in events]
        pos = solve(pitches, args.tuning)
        tab = render(pos, args.tuning, labels=rhythm_labels(events, args.bpm))
        print(f"[4/4] tab rendered", file=sys.stderr)

    header = (f"# tuning: {args.tuning}  notes: {len(pos)}"
              + (f"  bpm: {args.bpm}" if args.bpm else ""))
    result = header + "\n\n" + tab
    if args.out:
        Path(args.out).write_text(result)
        json.dump(events, open(args.out + ".notes.json", "w"), indent=1)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
