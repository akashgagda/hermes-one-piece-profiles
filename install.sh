#!/usr/bin/env sh
set -eu

REPO_URL="https://github.com/akashgagda/hermes-one-piece-profiles.git"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CHECKOUT="${HERMES_ONE_PIECE_HOME:-$DATA_HOME/hermes-one-piece-profiles}"

if ! command -v git >/dev/null 2>&1; then
  printf '%s\n' "git is required." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "python3 is required." >&2
  exit 1
fi
if ! command -v hermes >/dev/null 2>&1; then
  printf '%s\n' "Hermes Agent is required: https://hermes-agent.nousresearch.com/docs/" >&2
  exit 1
fi

if [ -d "$CHECKOUT/.git" ]; then
  printf '%s\n' "Using existing checkout at $CHECKOUT (not pulling code automatically)."
elif [ -e "$CHECKOUT" ]; then
  printf '%s\n' "$CHECKOUT exists but is not this collection's git checkout." >&2
  exit 1
else
  mkdir -p "$(dirname "$CHECKOUT")"
  git clone --depth 1 "$REPO_URL" "$CHECKOUT"
fi

exec python3 "$CHECKOUT/manage.py" install "$@"
