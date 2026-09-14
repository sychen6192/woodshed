#!/usr/bin/env bash
# install.sh - install the youtube-bass-tab skill.
#
#   bash install.sh                       # Hermes:  ~/.hermes/skills/music/youtube-bass-tab
#   bash install.sh --target hermes       # same
#   bash install.sh --target claude       # Claude Code, this project:  ./.claude/skills/...
#   bash install.sh --target claude-user  # Claude Code, all projects:  ~/.claude/skills/...
#   bash install.sh /some/path            # anywhere you like
#   SKIP_SETUP=1 bash install.sh          # copy only, build the Python env later
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="youtube-bass-tab"
HERMES_DEST="$HOME/.hermes/skills/music/$NAME"

TARGET="hermes"; DEST=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2;;
    -h|--help) sed -n '2,12p' "$0"; exit 0;;
    -*) echo "unknown option $1"; exit 2;;
    *) DEST="$1"; TARGET="explicit"; shift;;
  esac
done

case "$TARGET" in
  hermes)      DEST="$HERMES_DEST";;
  claude)      DEST="$PWD/.claude/skills/$NAME";;
  claude-user) DEST="$HOME/.claude/skills/$NAME";;
  explicit)    ;;
  *) echo "unknown --target $TARGET (hermes | claude | claude-user)"; exit 2;;
esac

mkdir -p "$(dirname "$DEST")"
if [[ "$SRC" != "$DEST" ]]; then
  rm -rf "$DEST"
  cp -R "$SRC" "$DEST"
  find "$DEST" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
fi
chmod +x "$DEST"/install.sh "$DEST"/scripts/*.sh
echo "[install] skill copied to $DEST"

# SKILL.md refers to scripts as $SKILL_DIR/scripts/... . Claude Code knows where
# the skill lives and resolves that itself, so leave the token alone there; a
# Hermes agent does not, so stamp the absolute path in.
if [[ "$TARGET" == "hermes" || "$TARGET" == "explicit" ]]; then
  perl -pi -e "s#\\\$SKILL_DIR#$DEST#g" "$DEST/SKILL.md"
  echo "[install] stamped absolute paths into SKILL.md"
fi

if [[ "${SKIP_SETUP:-0}" == "1" ]]; then
  echo "[install] SKIP_SETUP=1 -> run  bash $DEST/scripts/setup.sh  later"
else
  bash "$DEST/scripts/setup.sh"
fi

case "$TARGET" in
  hermes|explicit) cat <<EOF

[install] next steps
  1. restart the Hermes gateway (systemctl --user restart <your-gateway-unit>) or open a new session
  2. check:  hermes skills list | grep $NAME
  3. in Telegram, send a YouTube link and ask for the bass tab
EOF
;;
  claude|claude-user) cat <<EOF

[install] next steps
  1. start a new Claude Code session (skills are picked up at startup)
  2. check:  /skills   (look for $NAME)
  3. paste a YouTube link and ask for the bass tab
EOF
;;
esac
