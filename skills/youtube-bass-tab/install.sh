#!/usr/bin/env bash
# install.sh - install the youtube-bass-tab skill into Hermes Agent.
#
#   bash install.sh                                    # -> ~/.hermes/skills/music/youtube-bass-tab
#   bash install.sh ~/.hermes/profiles/NAME/skills/music/youtube-bass-tab   # named profile
#   SKIP_SETUP=1 bash install.sh                       # copy only, no Python setup
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT="$HOME/.hermes/skills/music/youtube-bass-tab"
DEST="${1:-$DEFAULT}"

mkdir -p "$(dirname "$DEST")"
if [[ "$SRC" != "$DEST" ]]; then
  rm -rf "$DEST"
  cp -R "$SRC" "$DEST"
fi
chmod +x "$DEST"/install.sh "$DEST"/scripts/*.sh

# SKILL.md refers to the default path; rewrite it if installed somewhere else
if [[ "$DEST" != "$DEFAULT" ]]; then
  perl -pi -e "s#~/.hermes/skills/music/youtube-bass-tab#$DEST#g" "$DEST/SKILL.md"
fi
echo "[install] skill copied to $DEST"

if [[ "${SKIP_SETUP:-0}" == "1" ]]; then
  echo "[install] SKIP_SETUP=1 -> run  bash $DEST/scripts/setup.sh  later"
else
  bash "$DEST/scripts/setup.sh"
fi

cat <<EOF

[install] next steps
  1. restart the Hermes gateway (systemctl --user restart <your-gateway-unit>) or open a new session
  2. check:  hermes skills list | grep youtube-bass-tab
  3. in Telegram, send a YouTube link and ask for the bass tab
EOF
