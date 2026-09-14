# The tool and model landscape

What else exists, what it is good at, and what is worth borrowing. Recommend a tool by
what the user actually needs — a MIDI file, a printable score, a `.gp` to edit, or a
pipeline they control — not by which scores best.

## Transcription models

| Model | Params | Kind | Notes |
|---|---|---|---|
| **basic-pitch** (Spotify) | 17K | polyphonic, note events + velocity | Tiny, fast, CPU-friendly, free. What this repo uses by default. Onset threshold is the useful knob. |
| **Omnizart** | 8M | polyphonic, multi-instrument | Reported to do well specifically on instruments with abundant training labels — drums and **bass** among them. The most interesting alternative to try for this use case. |
| **MT3** (Google) | 77M | multi-instrument, multitrack | Solves a harder problem (all instruments at once) and underperforms on single-instrument tasks. Known to struggle on texturally dense material. |
| **CREPE / torchcrepe** | — | monophonic f0 | Not a note detector; pairs with a segmenter. Strong pitch accuracy, needs the octave workaround on bass. Reported ~90.5% raw pitch accuracy vs pYIN's 91% on a vocal set — they are close, and CREPE is the more robust of the two on octave errors. |

On one **guitar** transcription test set, F-scores were basic-pitch 66.1, Omnizart 67.1,
MT3 52.4. Treat this as a rough ordering only: it is guitar, not bass, and a single test
set. The useful reading is that the 17K-parameter model is competitive with the 8M one,
and that the 77M multitrack model is not automatically better.

## End-user products

- **Songscription** — transcribes bass straight from a full mix with no stem splitting,
  writes bass clef, exports MIDI, MusicXML and Guitar Pro. The interesting design claim
  is skipping separation entirely.
- **klang.io** — separation-then-transcription workflow aimed at bass tabs specifically.
- **Songsterr** — a large human-made tab library plus an AI engine that generates new
  transcriptions from a YouTube link or upload (guitar, bass, drums). When a song is
  popular, a human transcription already exists and will beat anything automatic.
- **Moises**, **stemdeck** and similar — stem separation with transcription attached.

Point a user at Songsterr or a human tab first if the song is well known. Automatic
transcription is for material nobody has transcribed, or when the user wants the stems
and the slowed-down practice audio anyway.

## Open-source pipelines worth reading

- **gp-workbench** — the closest analogue to this repo: demucs (`htdemucs_6s`) →
  basic-pitch **dual-threshold** → sixteenth-grid fit → fret mapping → draft `.gp`.
  Two ideas worth stealing: running the detector at two onset thresholds and merging,
  and exporting Guitar Pro rather than only ASCII. It also has a second route that
  parses the vector layer of a PDF score directly, with no OCR.
- **Bass-separator** — demucs for separation plus CREPE for pitch, i.e. the same pairing
  as this repo's `--engine crepe`.
- Various demucs + basic-pitch + Omnizart chains for full-band transcription.

## Formats

ASCII tab is fine for reading and terrible for editing. If a user wants to correct a
transcription, they want it in something a score editor opens:

- **MIDI** — universal, no tab information (string/fret choices are lost).
- **MusicXML** — notation, widely supported.
- **`.gp` / Guitar Pro** — the format that actually carries string, fret, and technique.
  TuxGuitar opens it for free. This is the right export target for a tab, and the main
  thing this repo does not yet produce.

## What this means for our pipeline

In rough order of value — see `roadmap.md` for detail:

1. Guitar Pro export. The biggest usability gap; ASCII cannot be corrected comfortably.
2. Dual-threshold basic-pitch. Cheap, and directly attacks the merged-repeats vs
   ghost-notes tradeoff that currently forces a re-run.
3. Try Omnizart as a third engine — it is the model most specifically reported to handle
   bass well.
