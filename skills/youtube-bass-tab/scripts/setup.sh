#!/usr/bin/env bash
# setup.sh - create the Python environment for youtube-bass-tab and run the self-test.
# Safe to re-run. Needs: bash, curl, ffmpeg. Works on Linux, macOS, WSL. GPU optional.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${BASSENV:-$HOME/.venvs/basstab}"
OS="$(uname -s)"

say() { echo "[setup] $*"; }

# 1. ffmpeg
if ! command -v ffmpeg >/dev/null; then
  echo "[setup] ffmpeg is missing. Install it first:"
  echo "        Ubuntu/Debian: sudo apt install -y ffmpeg     macOS: brew install ffmpeg"
  exit 1
fi

# 2. uv (fast Python installer; also fetches Python 3.11 for us)
if ! command -v uv >/dev/null; then
  say "installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
command -v uv >/dev/null || { echo "[setup] uv not on PATH; open a new shell and re-run"; exit 1; }

# 3. venv - basic-pitch requires Python <= 3.11
say "creating venv at $VENV (Python 3.11)"
uv venv -q -p 3.11 "$VENV"
export VIRTUAL_ENV="$VENV"

# 4. torch: NVIDIA -> CUDA 12.8 wheels; Linux without NVIDIA -> small CPU wheels; macOS -> default
if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
  say "NVIDIA GPU detected -> CUDA torch"
  uv pip install -q torch torchaudio --index-url https://download.pytorch.org/whl/cu128
elif [[ "$OS" == "Linux" ]]; then
  say "no NVIDIA GPU -> CPU torch (demucs takes 1-5 min per song, that is fine)"
  uv pip install -q torch torchaudio --index-url https://download.pytorch.org/whl/cpu
else
  uv pip install -q torch torchaudio
fi

# 5. transcription stack
#    setuptools<81 is required: newer versions dropped pkg_resources, which resampy imports.
say "installing demucs, basic-pitch, yt-dlp, librosa"
if [[ "$OS" == "Darwin" ]]; then BP="basic-pitch[coreml]"; else BP="basic-pitch"; fi
uv pip install -q demucs "$BP" pretty_midi soundfile librosa yt-dlp "setuptools<81"

# 6. self-test (no download, no GPU needed)
say "running self-test"
"$VENV/bin/python" "$HERE/selftest.py"
say "done. Restart the Hermes gateway (or start a new session) so the skill is picked up."
