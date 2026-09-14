---
name: youtube-bass-tab
description: >-
  Transcribe a bass line from a YouTube link or an audio file into an ASCII bass tab
  plus a practice pack (isolated bass mp3, bass-less backing track, 0.75x slowed
  versions, cleaned MIDI). Everything runs locally on this host with one script
  (yt-dlp -> demucs -> basic-pitch -> tab renderer). Use whenever the user sends a
  YouTube link and wants the bass part / bass tab / 扒譜 / 扒bass / 貝斯譜 / 練歌包 /
  我想學這首的 bass, or asks to re-run a tab with a different tuning, BPM or sensitivity.
version: 1.0.0
author: sychen
---

# youtube-bass-tab

One script does everything: `~/.hermes/skills/music/youtube-bass-tab/scripts/basstab.sh`.
It downloads the audio, isolates the bass with demucs (GPU if present, otherwise CPU),
transcribes it with basic-pitch, renders a playable tab (harmonic ghost notes removed,
grid quantized, frets chosen for minimal hand movement) and encodes an mp3 practice pack.
Outputs land in `~/tabwork/<slug>/out/` on this host, so they can be attached directly.

## 1. Run

```bash
bash ~/.hermes/skills/music/youtube-bass-tab/scripts/basstab.sh "<URL>" --slug <short-ascii-name>
```

Give the terminal tool a long timeout (900 s): a song takes ~1 min on a GPU, 2-5 min on
CPU. If the terminal tool can run commands in the background, do that and poll.

Optional flags: `--tuning EADG|BEADG|DADG|EbAbDbGb` `--bpm N` `--onset 0.4..0.7`
`--min-note-ms 40..80` `--grid 12|16|24` `--transpose -12` `--no-separate` (source is
already bass-only, e.g. a bass cover or isolated track) `--cpu` `--force`.
Re-runs with new flags are fast: download and separation are cached per slug.

If the user uploaded an audio file instead of a link, pass its path: `--input <file>`.

The script prints progress lines, a tab preview, and finally ONE line:
`RESULT {"ok":true,"slug":..,"out_dir":..,"tab":..,"files":[..],"summary":..}`
If `ok` is false or there is no RESULT line, report the error text and stop.
Never say the tab is ready without an `ok:true` RESULT.

## 2. Deliver

Reply with, in this order:
1. The first ~8 bars of the tab (from the preview or `head -n 14 <tab>`) inside a
   ``` code block. Keep the whole message under 3500 chars; the full tab is attached.
2. The summary in plain words: note count, BPM and its source, harmonics dropped,
   octave folds. If octave_folds is more than ~15% of the notes, say the line may be an
   octave off and offer a re-run with `--transpose -12`.
3. One `MEDIA:` tag per file, using the absolute paths from the RESULT `files` list:
   `<slug>.tab.txt`, `<slug>.bass.mp3`, `<slug>.backing_nobass.mp3`,
   `<slug>.bass_slow75.mp3`, `<slug>.cleaned.mid` (backing_nobass is absent when
   `--no-separate` was used). Only list files that exist.
4. One line: this is a draft to fix by ear against bass.mp3; backing_nobass.mp3 is the
   play-along track; cleaned.mid opens in TuxGuitar / Guitar Pro.

## 3. Fix loop

| User says | Re-run with |
|---|---|
| repeated notes got merged into one | `--onset 0.4` |
| ghost notes / noise in the tab | `--onset 0.7` |
| whole line an octave too high (synth bass) | `--transpose -12` |
| tempo wrong / doubled / halved | `--bpm N` |
| song is in Eb / drop D / 5-string | `--tuning EbAbDbGb` / `DADG` / `BEADG` |
| swing or triplet feel looks smeared | `--grid 12` |

## 4. Failures

| Symptom | Action |
|---|---|
| RESULT error `venv not found` | tell the user to run `bash ~/.hermes/skills/music/youtube-bass-tab/scripts/setup.sh` |
| RESULT error mentions ffmpeg | `sudo apt install ffmpeg` (or `brew install ffmpeg`) |
| RESULT error mentions yt-dlp | link is bad, private or age-gated; ask for another link or a file upload |
| RESULT error mentions demucs / CUDA / out of memory | re-run with `--cpu` |
| Command timed out | re-run once with a longer timeout or in the background; the cache means it resumes where it stopped |
| MEDIA file not attached | the path must exist on this host; check with `ls` before replying |

Personal practice use only. Expect an ~80% draft, not a finished score.
