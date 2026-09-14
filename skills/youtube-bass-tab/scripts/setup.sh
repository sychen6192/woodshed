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

# 4. torch: NVIDIA -> CUDA 12.8 wheels; Linux without NVIDIA -> small CPU wheels; macOS -> default.
#    TORCH_INDEX_URL overrides the choice: set it to "" for plain PyPI (works where a proxy
#    blocks download.pytorch.org; on Linux that is the CUDA build, ~7 GB installed), or to an
#    internal mirror.
if [[ -n "${TORCH_INDEX_URL+x}" ]]; then
  INDEX="$TORCH_INDEX_URL"
  say "torch index from TORCH_INDEX_URL: ${INDEX:-PyPI}"
elif command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
  say "NVIDIA GPU detected -> CUDA torch"
  INDEX="https://download.pytorch.org/whl/cu128"
elif [[ "$OS" == "Linux" ]]; then
  say "no NVIDIA GPU -> CPU torch (demucs takes 1-5 min per song, that is fine)"
  INDEX="https://download.pytorch.org/whl/cpu"
else
  INDEX=""
fi
IDX=(); [[ -n "$INDEX" ]] && IDX=(--index-url "$INDEX")
if ! uv pip install -q torch torchaudio ${IDX[@]+"${IDX[@]}"}; then
  echo "[setup] torch install failed${INDEX:+ from $INDEX}."
  echo "        If your network blocks that host, retry with:   TORCH_INDEX_URL= bash $0"
  exit 1
fi

# 5. transcription stack
#    setuptools<81 is required: newer versions dropped pkg_resources, which resampy imports.
#    torchcrepe drives the second engine (--engine crepe); matplotlib draws the PNG tab.
#    Tempo is our own onset-envelope code now, so nothing here calls librosa directly
#    (basic-pitch still pulls it in as a dependency of its own).
say "installing demucs, basic-pitch, torchcrepe, yt-dlp"
if [[ "$OS" == "Darwin" ]]; then BP="basic-pitch[coreml]"; else BP="basic-pitch"; fi
uv pip install -q demucs "$BP" torchcrepe pretty_midi soundfile numpy scipy matplotlib \
  yt-dlp "setuptools<81"

# 6. self-test (no download, no GPU needed)
say "running self-test"
"$VENV/bin/python" "$HERE/selftest.py"
say "done. Restart the Hermes gateway (or start a new session) so the skill is picked up."
