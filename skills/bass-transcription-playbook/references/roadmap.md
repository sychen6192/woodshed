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

## Next

**1. Guitar Pro export.** The biggest gap. ASCII is unreadable to edit and MIDI loses
the string/fret choice the solver just made. `PyGuitarPro` writes `.gp5`; the
`events` list after `map_frets()` already carries `(slot, pitch, duration, velocity,
(string, fret))`, which is everything a `.gp` beat needs. Blocked on being able to open
the output in Guitar Pro or TuxGuitar to confirm it is well-formed — do not ship this
untested, a malformed `.gp` fails silently.

**2. Dual-threshold basic-pitch.** Run the detector at ~0.4 and ~0.7 and merge: take
the union of onsets, keep the high-threshold note when both fire. This directly removes
the merged-repeats-vs-ghost-notes tradeoff that currently costs a re-run. Cheap — it is
a second `basic-pitch` invocation and a merge pass. Borrowed from gp-workbench.

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

## Known-unverified

- **`--engine crepe` has never run end to end.** The glue is tested (crepe-shaped events
  produce the same tab as basic-pitch-shaped ones), but `pitch.py` itself needs torch
  and torchcrepe, which the development environment did not have. First real run should
  compare both engines on the same song before the flag is recommended to anyone.
- **`selftest.py`** (the full-pipeline one) has not been re-run since the changes; it
  needs demucs and basic-pitch. Its assertion is on the summary's `notes=N` field, which
  is unchanged, so it should still pass, but that is an argument not a test.
- Tempo and downbeat are verified only against synthesized audio with a rigid grid.
  Real drums, rubato and swing are untested.
