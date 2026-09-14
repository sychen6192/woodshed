# bass-tab

Turning a song into a playable bass tab. The repo holds two implementations of
that idea, which grew up separately and are now side by side:

|                | `*.py` at the root                  | `skills/youtube-bass-tab/`                     |
| -------------- | ----------------------------------- | ---------------------------------------------- |
| What it is     | research pipeline / library         | packaged agent skill (Hermes)                  |
| Transcriber    | torchcrepe (monophonic f0)          | basic-pitch (polyphonic → MIDI)                |
| Tempo          | `tempo.py` / `rhythm.py`            | librosa `beat_track`                           |
| Output         | ASCII tab, typeset PNG              | ASCII tab, mp3 practice pack, cleaned MIDI     |
| Entry point    | `python bass2tab.py <url\|file>`    | `bash scripts/basstab.sh "<url>"`              |
| Environment    | whatever you have installed         | pinned venv built by `scripts/setup.sh`        |

Both follow the same shape — yt-dlp → demucs → transcribe → fret solver → tab —
but they share no code. [`docs/integration.md`](docs/integration.md) works
through what actually overlaps and what merging them would involve.

## Layout

```
bass2tab.py        CLI: source audio → isolated bass → notes → ASCII tab
pitch.py           torchcrepe f0 tracking, with the octave-shift trick for bass
fretboard.py       Viterbi fret solver + ASCII renderer
tempo.py           spectral-flux onset envelope, autocorrelation tempo, beat phase
rhythm.py          tempo from note onsets, downbeat search, grid quantization
render_tab.py      typeset PNG tab (matplotlib)
make_test.py       synthesizes test_bass.wav with a known 16-note ground truth

cover.tab, tab_p*.png, cover_tab.pdf, ...   sample output kept for reference

skills/youtube-bass-tab/   the agent skill — see its own README
docs/integration.md        how the two halves relate
```

Only `bass2tab.py → fretboard.py` is wired together today. `tempo.py`,
`rhythm.py` and `render_tab.py` work but nothing calls them; they are reached by
importing them yourself.

## Running the research pipeline

Needs `ffmpeg`, `yt-dlp`, and a Python env with `torch`, `torchcrepe`,
`soundfile`, `scipy`, `numpy`, `demucs` (plus `matplotlib` for `render_tab.py`).

```bash
python bass2tab.py "<youtube-url>" -o out.tab
python bass2tab.py song.wav --tuning standard5 --bpm 96 -o out.tab
python bass2tab.py bass_only.wav --skip-demucs --device cpu -o out.tab
```

`--device` defaults to `cuda`; pass `--device cpu` if you have no GPU. Writes
`out.tab` and `out.tab.notes.json` (the raw note events).

Tunings: `standard4` (EADG), `drop_d4` (DADG), `standard5` (BEADG).

Sanity check without any audio, since `fretboard.py` is pure stdlib:

```bash
python fretboard.py        # chromatic run + an octave leap
python make_test.py        # writes test_bass.wav + test_truth.txt
```

## Running the skill

Self-contained: it builds its own Python 3.11 venv at `~/.venvs/basstab` and
installs itself into `~/.hermes/skills/music/youtube-bass-tab`.

```bash
bash skills/youtube-bass-tab/install.sh
```

Then, from the repo or anywhere:

```bash
bash ~/.hermes/skills/music/youtube-bass-tab/scripts/basstab.sh "<url>" --slug song
```

Outputs land in `~/tabwork/<slug>/out/`. Download and stem separation are cached
per slug, so re-running with different knobs (`--onset`, `--bpm`, `--tuning`,
`--transpose`, `--grid`) only costs the transcription step. Full usage,
troubleshooting and the fix-it-by-ear loop are in
[`skills/youtube-bass-tab/README.md`](skills/youtube-bass-tab/README.md).

## Expectations

Automatic transcription tops out around 80% correct on a normal mix, and drops
where the bass shares space with the kick or a synth. Treat the output as a
draft to correct by ear against the isolated bass stem. Personal practice use.
