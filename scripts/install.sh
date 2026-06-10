#!/usr/bin/env bash
# Install memory-solution skills into the user's home so pi can discover
# them. Renders SKILL.md files with vars from
# scripts/config/install.yaml (overridable via env or
# ~/.config/memory-solution/install.yaml) and copies each skill into
# the first available global skills root:
#
#   1. ~/.agents/skills/         (pi's default per docs)
#   2. ~/.pi/agent/skills/       (fallback; also discovered by pi)
#
# Re-running is safe: existing files in the destination are overwritten
# by the source-of-truth copy. To uninstall, remove the skill
# directories from the install root.
#
# Usage:
#   bash scripts/install.sh              # install
#   bash scripts/install.sh --dry-run    # show what would happen
#   MEMORY_VAULT_ROOT=~/other bash scripts/install.sh
#                                      # override vault_root for this run

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required" >&2
  exit 1
fi

# Pick the first available install root. We prefer ~/.agents/skills/ as
# the docs call it out, falling back to ~/.pi/agent/skills/ if needed.
INSTALL_ROOT=""
for candidate in "$HOME/.agents/skills" "$HOME/.pi/agent/skills"; do
  INSTALL_ROOT="$candidate"
  break
done

if [[ -z "$INSTALL_ROOT" ]]; then
  echo "error: no install root candidate found" >&2
  exit 1
fi

DRY_RUN_FLAG=""
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN_FLAG="--dry-run"
fi

echo "Install root: $INSTALL_ROOT"
echo

# Make sure the install root exists (only when actually installing).
if [[ -z "$DRY_RUN_FLAG" ]]; then
  mkdir -p "$INSTALL_ROOT"
fi

python3 "$SCRIPT_DIR/render.py" \
  --skills-src "$PROJECT_ROOT/skills" \
  --dest "$INSTALL_ROOT" \
  $DRY_RUN_FLAG

echo
echo "Verify with:  ls $INSTALL_ROOT"
echo "Then in pi, the skills should appear in the system prompt and as"
echo "  /skill:<name> commands. If they don't, check ~/.pi/settings.json"
echo "  for the 'skills' array (see pi's skills.md for the format)."
