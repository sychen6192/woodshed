# What to change in youtube-bass-tab next

State of the pipeline as it stands, and the next moves in order of value per unit of
risk. Keep this file honest — move items from "next" to "done" only when something
actually verifies them.

## Done

| Change | What it bought |
|---|---|
| One tuning table in `lib/fretboard.py` | `EADG` and `standard4` are the same thing; every entry point takes either spelling, plus `EbAbDbGb` and a raw `28,33,38,43`. |
| `--png` via `lib/render_tab.py` | A typeset tab image alongside the ASCII one. The adapter is one line: `[(e[0], e[4]) for e in events]`. |
| Tempo from `lib/tempo.py` | Spectral-flux onset envelope + autocorrelation, numpy only. Nothing in our code calls librosa now (basic-pitch still pulls it in as its own dependency). |
| Frame-centre fix in `tempo.py` | A spectral-flux frame's energy belongs to the frame's centre, not its start. Attributing it to the start read every onset ~60 ms early and dragged the beat phase with it. |
| Downbeat from note weight (`rhythm.downbeat_from_notes`) | Bar 1 is found rather than assumed to be t=0. Scores candidate phases by velocity × duration × lowness, which resolves the beat-vs-bar ambiguity that onset energy alone cannot. Walks back whole bars so a pickup is not dropped. |
| Register warnings in `midi_to_basstab.py` | The renderer now names the likely cause: notes below the low string → a tuning suggestion; a high centre of mass → a synth-bass octave error; notes past the top fret → `--frets`/`--transpose`. |
| `--engine crepe` | torchcrepe reaches the same renderer through `lib/crepe_to_midi.py`, which emits MIDI in the shape basic-pitch produces. Confidence maps onto velocity so the downstream filters still have something to work with. |
| `scripts/selftest_offline.py` | Everything above is checked against synthesized audio with a known tempo, downbeat and note list, needing no demucs/basic-pitch/torch. |
| `TORCH_INDEX_URL` in `setup.sh` | Behind a proxy that blocks download.pytorch.org the old script died with a raw uv error. Now `TORCH_INDEX_URL= bash setup.sh` falls back to PyPI (the CUDA build on Linux, ~7 GB) and the failure message says so. |
| Network-aware failures in `basstab.sh` | A blocked yt-dlp or demucs weight download used to be reported as "bad link" / "retry with --cpu". run.log is now checked for proxy/DNS signatures and the RESULT names the unreachable host. Reproduced both failures to confirm. |
| Walk-back tolerance in `detect_tempo` | 8 ms of onset jitter before a correctly found downbeat used to step bar 1 back a whole bar, so the tab opened with an empty bar. A note within half a slot of the bar line rounds to slot 0 anyway, so it no longer counts. |
| Crepe velocity from loudness | Periodicity mapped onto velocity came out flat (114-117 for every note), which left `downbeat_from_notes` with no accent and it chose the "and" of 1 on a root-root line. `crepe_to_midi.py` now takes each note's RMS at onset. |

## Next

**1. Guitar Pro export.** The biggest gap. ASCII is unreadable to edit and MIDI loses
the string/fret choice the solver just made. `PyGuitarPro` writes `.gp5`; the
`events` list after `map_frets()` already carries `(slot, pitch, duration, velocity,
(string, fret))`, which is everything a `.gp` beat needs. Blocked on being able to open
the output in Guitar Pro or TuxGuitar to confirm it is well-formed — do not ship this
untested, a malformed `.gp` fails silently.

**2. Dual-threshold basic-pitch.** Run the detector at ~0.4 and ~0.7 and merge: take
the union of onsets, keep the high-threshold note when both fire. Measured need: on a
96-note line, onset 0.5 gave 16 ghosts and 3 misses; onset 0.7 gave 7 ghosts and 14
misses (it merged repeated low notes) and moved the downbeat. Neither setting is right,
and the merge would take the best of both. Cheap — a second `basic-pitch` invocation
and a merge pass. Borrowed from gp-workbench.

**3. Omnizart as a third engine.** It is the model most specifically reported to do well
on bass. The engine seam already exists (`--engine`), so this is a `lib/omnizart_to_midi.py`
that emits the same MIDI shape. Weigh the install cost first: 8M parameters and its own
dependency stack against basic-pitch's 17K.

**4. Act on the tuning hint instead of only printing it.** The detector is reliable in
testing (drop D, half-step-down and 5-string all identified from the note list alone).
An `--auto-tuning` flag that re-runs the fret mapping with the suggested tuning would
save the user a round trip. Keep it opt-in: guessing the tuning wrong is worse than
asking.

**5. Technique.** Slides, hammer-ons, pull-offs, dead notes and dynamics are not in the
note list at all, and their absence is most of what separates a draft from a usable
score. Legato is partly inferable — a pitch change with no new onset inside one note
envelope is a slide or a hammer-on. Real work, and the first thing here that needs
training data rather than heuristics.

## Measured

Synthetic line, 96 notes over 12 bars at 96 BPM, downbeat at 1.10 s, onsets humanized
by ±8 ms, run through the installed skill on CPU. Scored by matching each true note to a
transcribed one within 90 ms. Reproduce with `scripts/bench/make_mix.py` (writes the mix,
the bass-only stem and `truth.json`) and `scripts/bench/score.py`.

| Engine | Found | Exact pitch | Octave errors | Ghosts | Tempo | Bar 1 | Wall time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| basic-pitch, onset 0.5 | 93/96 | 92 | 0 | 16 | 96.1 | 1.09 s | 14 s |
| basic-pitch, onset 0.7 | 82/96 | 80 | 1 | 7 | 96.1 | 0.82 s (wrong) | 14 s |
| crepe, conf 0.55 | 85/96 | 85 | 0 | 0 | 96.1 | 1.09 s (0.78 s before the loudness fix) | 1 m 44 s |

basic-pitch's misses are all the second note of a repeated E1 pair — the lowest note
in the line, the hardest to re-trigger. crepe's misses are all repeated pairs and one
run of three D2s across a bar line: a pitch tracker cannot see a repeat.

## Still unverified

- **demucs separation.** The weight host (dl.fbaipublicfiles.com) was unreachable from
  the verification environment, so the mix-with-separation run could only prove the
  failure path. The bass-only runs above skip separation. First run on a machine that
  can fetch the weights should use a mix with a kick drum on the bass notes.
- **YouTube download.** Same reason. The URL path was exercised only as far as
  yt-dlp's failure report.
- **Real drums, rubato, swing.** Tempo and downbeat are verified on two synthetic sets
  only, both with a rigid grid.
- **Crepe on a real stem.** It has run end to end on synthesized bass; a separated stem
  with bleed is the next test.
