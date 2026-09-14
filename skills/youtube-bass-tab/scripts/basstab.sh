#!/usr/bin/env bash
# basstab.sh - one-shot: YouTube URL (or --input FILE) -> bass tab + practice pack.
# Runs on the llm workstation. Prints progress, a tab preview, then ONE final line:
#   RESULT {"ok":true|false, ...}
# Download and stem separation are cached per slug, so re-runs with new knobs are fast.
set -uo pipefail

BASSENV="${BASSENV:-$HOME/.venvs/basstab}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAB_PY="${TAB_PY:-$SCRIPT_DIR/midi_to_basstab.py}"
ROOT="${BASSTAB_ROOT:-$HOME/tabwork}"

usage() {
  cat <<EOF
usage: basstab.sh <youtube-url> | --input FILE  [options]
  --slug NAME          working-dir name (default: ascii title, else video id)
  --tuning EADG        EADG | BEADG | DADG | EbAbDbGb | 28,33,38,43
  --bpm N              force tempo (default: librosa on the mix)
  --onset 0.5          basic-pitch onset threshold (0.4 splits repeats, 0.7 kills ghosts)
  --min-note-ms 60     basic-pitch minimum note length
  --grid 16            tab grid: 16 straight, 12/24 swing
  --transpose N        semitones before fret mapping (-12 for octave-high synth bass)
  --no-separate        source is already bass-only (bass cover / isolated track)
  --cpu                run demucs on CPU (GPU busy)
  --force              re-download / re-separate even if cached
EOF
}

URL=""; INPUT=""; SLUG=""; TUNING="EADG"; BPM=""; ONSET="0.5"; MINNOTE="60"
GRID="16"; TRANSPOSE="0"; SEPARATE=1; DEVICE=(); FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --input) INPUT="$2"; shift 2;;
    --slug) SLUG="$2"; shift 2;;
    --tuning) TUNING="$2"; shift 2;;
    --bpm) BPM="$2"; shift 2;;
    --onset) ONSET="$2"; shift 2;;
    --min-note-ms) MINNOTE="$2"; shift 2;;
    --grid) GRID="$2"; shift 2;;
    --transpose) TRANSPOSE="$2"; shift 2;;
    --no-separate) SEPARATE=0; shift;;
    --cpu) DEVICE=(-d cpu); shift;;
    --force) FORCE=1; shift;;
    -h|--help) usage; exit 0;;
    -*) echo "unknown option $1"; usage; exit 2;;
    *) URL="$1"; shift;;
  esac
done

fail() { echo "RESULT {\"ok\":false,\"error\":\"$1\",\"log\":\"${LOG:-}\"}"; exit 1; }
step() { echo "[basstab] $*"; }
[[ -n "$URL" || -n "$INPUT" ]] || { usage; fail "no input given"; }
[[ -x "$BASSENV/bin/python" ]] || fail "venv not found at $BASSENV"
command -v ffmpeg >/dev/null || fail "ffmpeg not installed"

# ---- slug --------------------------------------------------------------------
if [[ -z "$SLUG" ]]; then
  if [[ -n "$INPUT" ]]; then
    SLUG="$(basename "${INPUT%.*}")"
  else
    META="$("$BASSENV/bin/yt-dlp" --no-playlist --print "%(title)s|%(id)s" "$URL" 2>/dev/null)" \
      || fail "yt-dlp could not read the video (bad link, age gate, or yt-dlp outdated)"
    SLUG="${META%%|*}"; VID="${META##*|}"
  fi
fi
SLUG="$(printf '%s' "$SLUG" | iconv -f utf-8 -t ascii//TRANSLIT 2>/dev/null \
        | tr -cs 'A-Za-z0-9' '-' | sed 's/^-*//;s/-*$//' | cut -c1-60)"
[[ ${#SLUG} -ge 3 ]] || SLUG="${VID:-song-$(date +%s)}"
W="$ROOT/$SLUG"; OUT="$W/out"; LOG="$W/run.log"
mkdir -p "$OUT"; echo "=== $(date "+%Y-%m-%dT%H:%M:%S%z") $*" >> "$LOG"
step "slug=$SLUG workdir=$W"

# ---- 1. source audio ---------------------------------------------------------
if [[ -n "$INPUT" ]]; then
  [[ -f "$INPUT" ]] || fail "input file not found: $INPUT"
  if [[ ! -f "$W/song.wav" || $FORCE -eq 1 ]]; then
    step "converting input to wav"
    ffmpeg -y -loglevel error -i "$INPUT" -ac 2 -ar 44100 "$W/song.wav" >>"$LOG" 2>&1 \
      || fail "ffmpeg could not read input"
  fi
elif [[ ! -f "$W/song.wav" || $FORCE -eq 1 ]]; then
  step "downloading audio"
  "$BASSENV/bin/yt-dlp" -x --audio-format wav --no-playlist -o "$W/song.%(ext)s" "$URL" \
    >>"$LOG" 2>&1 || fail "yt-dlp download failed (see run.log)"
fi
[[ -f "$W/song.wav" ]] || fail "song.wav missing after download"

# ---- 2. bass stem ------------------------------------------------------------
NOBASS=""
if [[ $SEPARATE -eq 1 ]]; then
  BASS="$W/sep/htdemucs/song/bass.wav"; NOBASS="$W/sep/htdemucs/song/no_bass.wav"
  if [[ ! -f "$BASS" || $FORCE -eq 1 ]]; then
    step "separating bass stem (demucs${DEVICE[*]:+ ${DEVICE[*]}})"
    "$BASSENV/bin/demucs" --two-stems=bass -n htdemucs ${DEVICE[@]+"${DEVICE[@]}"} -o "$W/sep" "$W/song.wav" \
      >>"$LOG" 2>&1 || fail "demucs failed (see run.log; if CUDA/OOM, retry with --cpu)"
  fi
else
  BASS="$W/song.wav"
fi

# ---- 3. transcribe -----------------------------------------------------------
step "transcribing (basic-pitch onset=$ONSET min-note=${MINNOTE}ms)"
rm -rf "$W/bp"; mkdir -p "$W/bp"
"$BASSENV/bin/basic-pitch" "$W/bp" "$BASS" --save-midi \
  --onset-threshold "$ONSET" --minimum-note-length "$MINNOTE" \
  --minimum-frequency 30 --maximum-frequency 400 >>"$LOG" 2>&1 || fail "basic-pitch failed (see run.log)"
MID="$(ls "$W"/bp/*.mid 2>/dev/null | head -1)"
[[ -n "$MID" ]] || fail "basic-pitch produced no MIDI"

# ---- 4. tab ------------------------------------------------------------------
step "rendering tab (tuning=$TUNING grid=$GRID)"
if [[ -n "$BPM" ]]; then BPMARG=(--bpm "$BPM"); else BPMARG=(--audio "$W/song.wav"); fi
TAB="$OUT/$SLUG.tab.txt"
SUMMARY="$("$BASSENV/bin/python" "$TAB_PY" "$MID" "${BPMARG[@]}" --tuning "$TUNING" \
  --grid "$GRID" --transpose "$TRANSPOSE" --title "$SLUG" \
  -o "$TAB" --midi-out "$OUT/$SLUG.cleaned.mid" 2>&1 >/dev/null)" \
  || fail "tab render failed: $(printf '%s' "$SUMMARY" | tr '\n"' '  ')"
echo "$SUMMARY" >> "$LOG"

# ---- 5. practice pack (mp3 = small enough for Telegram) ----------------------
step "encoding practice pack"
mp3() { local extra=(); [[ -n "${3:-}" ]] && extra=(-af "atempo=$3")
        ffmpeg -y -loglevel error -i "$1" ${extra[@]+"${extra[@]}"} -codec:a libmp3lame -b:a 160k "$2" >>"$LOG" 2>&1; }
mp3 "$BASS" "$OUT/$SLUG.bass.mp3"
mp3 "$BASS" "$OUT/$SLUG.bass_slow75.mp3" 0.75
mp3 "$W/song.wav" "$OUT/$SLUG.song_slow75.mp3" 0.75
[[ -n "$NOBASS" && -f "$NOBASS" ]] && mp3 "$NOBASS" "$OUT/$SLUG.backing_nobass.mp3"

# ---- 6. report ---------------------------------------------------------------
echo "--- tab preview (first bars) ---"
head -n 14 "$TAB"
echo "--- $SUMMARY"
"$BASSENV/bin/python" - "$OUT" "$SLUG" "$SUMMARY" "$W" "$TAB" <<'EOF'
import json, sys, os, glob
out, slug, summary, w, tab = sys.argv[1:6]
files = sorted(glob.glob(os.path.join(out, "*")))
print("RESULT " + json.dumps({"ok": True, "slug": slug, "workdir": w, "out_dir": out,
      "tab": tab, "files": files, "summary": " | ".join(summary.strip().splitlines())}))
EOF
