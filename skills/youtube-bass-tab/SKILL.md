---
name: youtube-bass-tab
description: >-
  Transcribe a bass line from a YouTube link or an audio file into an ASCII bass tab,
  a typeset tab image and a practice pack (isolated bass mp3, bass-less backing track,
  0.75x slowed versions, cleaned MIDI). Everything runs locally on this host with one
  script (yt-dlp -> demucs -> basic-pitch or torchcrepe -> tab renderer). Use whenever
  the user sends a YouTube link and wants the bass part / bass tab / 扒譜 / 扒bass /
  貝斯譜 / 練歌包 / 我想學這首的 bass, or asks to re-run a tab with a different tuning,
  BPM, engine or sensitivity.
version: 2.0.0
author: sychen
---

# youtube-bass-tab

One script does everything: `$SKILL_DIR/scripts/basstab.sh`, where `$SKILL_DIR` is the
directory this SKILL.md sits in. It downloads the audio, isolates the bass with demucs
(GPU if present, otherwise CPU), transcribes it, finds the tempo and the downbeat,
renders a playable tab (harmonic ghost notes removed, grid quantized, frets chosen for
minimal hand movement) and encodes an mp3 practice pack. Outputs land in
`~/tabwork/<slug>/out/` on this host, so they can be attached directly.

## 1. Run

```bash
bash $SKILL_DIR/scripts/basstab.sh "<URL>" --slug <short-ascii-name>
```

Give the terminal tool a long timeout (900 s): a song takes ~1 min on a GPU, 2-5 min on
CPU. If the terminal tool can run commands in the background, do that and poll.

Optional flags: `--tuning EADG|BEADG|DADG|EbAbDbGb` `--bpm N` `--engine basic-pitch|crepe`
`--onset 0.4..0.7` `--conf 0.4..0.7` `--min-note-ms 40..80` `--grid 12|16|24`
`--transpose -12` `--no-separate` (source is already bass-only, e.g. a bass cover or
isolated track) `--cpu` `--force`. Re-runs with new flags are fast: download and
separation are cached per slug.

If the user uploaded an audio file instead of a link, pass its path: `--input <file>`.

The script prints progress lines, a tab preview, and finally ONE line:
`RESULT {"ok":true,"slug":..,"out_dir":..,"tab":..,"files":[..],"summary":..}`
If `ok` is false or there is no RESULT line, report the error text and stop.
Never say the tab is ready without an `ok:true` RESULT.

## 2. Deliver

Reply with, in this order:
1. The first ~8 bars of the tab (from the preview or `head -n 14 <tab>`) inside a
   ``` code block. Keep the whole message under 3500 chars; the full tab is attached.
2. The summary in plain words: note count, BPM and its source, where bar 1 starts,
   harmonics dropped, octave folds. Pass on any `[warn]` line — they are the ones that
   change what the user should do (see §3).
3. One `MEDIA:` tag per file, using the absolute paths from the RESULT `files` list:
   `<slug>.tab.txt`, `<slug>.tab.png`, `<slug>.bass.mp3`, `<slug>.backing_nobass.mp3`,
   `<slug>.bass_slow75.mp3`, `<slug>.cleaned.mid` (backing_nobass is absent when
   `--no-separate` was used). Only list files that exist.
4. One line: this is a draft to fix by ear against bass.mp3; backing_nobass.mp3 is the
   play-along track; cleaned.mid opens in TuxGuitar / Guitar Pro.

## 3. Fix loop

The renderer's `[warn]` lines already name the likely cause. Act on them first:

| Warning / symptom | Re-run with |
|---|---|
| `notes fall below the lowest open string ... may be in X` | `--tuning X` |
| `the line centres on ..., high for a bass` | `--transpose -12` |
| `notes sit past fret N and were folded down` | `--frets 24`, or `--transpose -12` |
| repeated notes got merged into one | `--onset 0.4` |
| ghost notes / a note repeated right after itself | `--onset 0.7`, then compare note counts: it also merges repeated notes on the low strings. If more real notes vanish than ghosts, use `--engine crepe` instead |
| tempo wrong / doubled / halved | `--bpm N` |
| bar lines land in the wrong place | `--bpm N` first; the downbeat is derived from it |
| swing or triplet feel looks smeared | `--grid 12` |
| the tab is full of doubled / re-triggered notes | `--engine crepe` |
| RESULT error says a host is unreachable or the network is blocked | no flag fixes this: yt-dlp or the demucs weight download could not get out; tell the user which host |

`--engine crepe` swaps basic-pitch for torchcrepe. Measured on a line with 96 known
notes: basic-pitch found 97% of them and added 16 ghost re-triggers; crepe found 89%,
invented nothing and got every pitch it reported right, but merges repeated notes,
because a pitch tracker only splits on a pitch change. Its velocities come from the
loudness of the audio at each onset, so accents and the downbeat still work. Use crepe
when the tab is full of doubled notes; stay on basic-pitch when the line leans on
repeats.

## 4. Failures

| Symptom | Action |
|---|---|
| RESULT error `venv not found` | tell the user to run `bash $SKILL_DIR/scripts/setup.sh` |
| setup.sh fails fetching from download.pytorch.org | the network blocks that host; re-run as `TORCH_INDEX_URL= bash $SKILL_DIR/scripts/setup.sh` (plain PyPI, ~7 GB on Linux) |
| RESULT error mentions ffmpeg | `sudo apt install ffmpeg` (or `brew install ffmpeg`) |
| RESULT error mentions yt-dlp | link is bad, private or age-gated; ask for another link or a file upload |
| RESULT error mentions demucs / CUDA / out of memory | re-run with `--cpu` |
| RESULT error mentions torchcrepe | re-run without `--engine crepe`, or with `--cpu` |
| Command timed out | re-run once with a longer timeout or in the background; the cache means it resumes where it stopped |
| MEDIA file not attached | the path must exist on this host; check with `ls` before replying |

Personal practice use only. Expect an ~80% draft, not a finished score. For what the
remaining 20% usually is and how to check a tab before trusting it, see the
`bass-transcription-playbook` skill.
