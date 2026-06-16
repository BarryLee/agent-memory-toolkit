#!/usr/bin/env bash
# Install memory-solution skills and scripts interactively.
#
# Skills are rendered (vars substituted) and copied to the pi skills
# root. Scripts are copied to ~/.local/bin/memory-solution/ and can be
# added to your PATH via shell alias.
#
# Usage:
#   bash scripts/install.sh              # interactive (default)
#   bash scripts/install.sh --auto       # non-interactive: install everything, no prompts
#   bash scripts/install.sh --dry-run     # show what would happen, no writes
#   bash scripts/install.sh --uninstall  # remove everything installed by this script
#
# Environment variables (override config):
#   MEMORY_VAULT_ROOT=~/other bash scripts/install.sh
#                                      # override vault_root for rendering

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_SRC="$PROJECT_ROOT/skills"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

confirm() {
  # Ask a yes/no/quit question. Returns 0 for yes, 1 for no, 2 for quit-all.
  local prompt="$1"
  local answer
  while true; do
    read -p "$prompt [y/n/q] " answer < /dev/tty
    case "$answer" in
      y|Y) return 0 ;;
      n|N) return 1 ;;
      q|Q) return 2 ;;
    esac
    echo "Please enter y, n, or q."
  done
}

add_aliases_to_shell() {
  # Use $SHELL (the user's login shell) to detect which shell to update.
  # We install to both ~/.bashrc and ~/.zshrc so it works regardless of
  # which shell the user actually starts. The marker block is identical
  # so uninstall works cleanly from either file.
  local rc_file=""   # suppress "unbound variable" under set -u
  local marker="# >>> memory-solution >>>"
  local end_marker="# <<< memory-solution <<<"

  local alias_block="
$marker
# Added by memory-solution install.sh
# Scripts: init_memory_bank.py, init_vault.py, promote.py, sync_raw.py
for _script in init_memory_bank.py init_vault.py promote.py sync_raw.py; do
  _path=\"$PROJECT_ROOT/scripts/\$_script\"
  if [[ -f \"\$_path\" ]]; then
    alias \"\$_script\"=\"python3 \\\"\$_path\\\"\"
    [[ \"\$_script\" == \"init_memory_bank.py\" ]] && alias \"\$_script-scaffold\"=\"python3 \\\"\$_path\\\" --scaffold\"
  fi
done
unset _script _path
$end_marker
"

  # Update both RC files; idempotent on re-runs (block replaced).
  for rc_file in "$HOME/.bashrc" "$HOME/.zshrc"; do
    # Remove any existing block first.
    if grep -q "$marker" "$rc_file" 2>/dev/null; then
      sed -i '' "/$marker/,/$end_marker/d" "$rc_file" 2>/dev/null \
        || sed -i "/$marker/,/$end_marker/d" "$rc_file"
    fi
    # Only append if the file exists and is writable.
    if [[ -f "$rc_file" && -w "$rc_file" ]]; then
      printf '%s' "$alias_block" >> "$rc_file"
      echo "  Aliases written to $rc_file."
    fi
  done
  echo "  Run 'source ~/.bashrc' and 'source ~/.zshrc', or start a new shell."
}

scaffold_missing_configs() {
  # Detect project config files that are missing but whose bundled
  # *.example.yaml is present, and offer to copy them. Behaviour
  # depends on $MODE:
  #   auto      -> copy silently
  #   dry-run   -> print what would be copied, no writes
  #   interactive -> ask per file
  # Idempotent: existing files are never touched.
  local config_dir="$PROJECT_ROOT/scripts/config"
  local real example

  for real in install.yaml sync.yaml staging-categories.yaml; do
    example="${real%.yaml}.example.yaml"
    [[ -f "$config_dir/$real" ]] && continue
    [[ -f "$config_dir/$example" ]] || continue

    case "$MODE" in
      auto)
        if cp "$config_dir/$example" "$config_dir/$real"; then
          echo "  copied: $real (from $example)"
        else
          echo "  error: failed to copy $example -> $real" >&2
        fi
        ;;
      dry-run)
        echo "  - $real (from $example)"
        ;;
      *)
        echo "Missing project config: $config_dir/$real"
        echo "  (a bundled $example is available with default values)"
        select answer in "Copy example to $real" "Skip" "Quit"; do
          case "$REPLY" in
            1) cp "$config_dir/$example" "$config_dir/$real" && echo "  copied."; break ;;
            2) echo "  skipped."; break ;;
            3) echo "Aborted."; exit 0 ;;
          esac
        done
        ;;
    esac
  done
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

MODE="interactive"  # interactive | auto | dry-run | uninstall

while [[ $# -gt 0 ]]; do
  case "$1" in
    --auto)     [[ "$MODE" == "interactive" ]] && MODE="auto" ;;
    --dry-run)  [[ "$MODE" == "interactive" ]] && MODE="dry-run" ;;
    --uninstall) [[ "$MODE" == "interactive" ]] && MODE="uninstall" ;;
    *)          echo "usage: install.sh [--auto|--dry-run|--uninstall]" >&2; exit 1 ;;
  esac
  shift
done

# ---------------------------------------------------------------------------
# Detect install roots
# ---------------------------------------------------------------------------

SKILLS_INSTALL_ROOT=""
for candidate in "$HOME/.agents/skills" "$HOME/.pi/agent/skills"; do
  if [[ -d "$candidate" || ! -e "$candidate" ]]; then
    SKILLS_INSTALL_ROOT="$candidate"
    break
  fi
done

if [[ -z "$SKILLS_INSTALL_ROOT" ]]; then
  echo "error: no skills install root available." >&2
  exit 1
fi

SCRIPTS_INSTALL_DIR="$HOME/.local/bin/memory-solution"

# ---------------------------------------------------------------------------
# Uninstall mode
# ---------------------------------------------------------------------------

if [[ "$MODE" == "uninstall" ]]; then
  echo "=== Uninstalling memory-solution ==="

  # Remove skills.
  for skill_dir in "$SKILLS_INSTALL_ROOT"/*; do
    [[ -d "$skill_dir" ]] || continue
    skill_name="$(basename "$skill_dir")"
    # Only remove skills that belong to this project (match the repo name).
    if [[ -f "$skill_dir/SKILL.md" ]] && grep -q "memory-solution" "$skill_dir/SKILL.md" 2>/dev/null; then
      echo "  removing skill: $skill_name"
      rm -rf "$skill_dir"
    fi
  done

  # Remove scripts.
  if [[ -d "$SCRIPTS_INSTALL_DIR" ]]; then
    echo "  removing scripts dir: $SCRIPTS_INSTALL_DIR"
    rm -rf "$SCRIPTS_INSTALL_DIR"
  fi

  # Remove aliases from shell RC files.
  for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    [[ -f "$rc" ]] || continue
    if grep -q "# >>> memory-solution >>>" "$rc" 2>/dev/null; then
      sed -i '' '/# >>> memory-solution >>>/,/# <<< memory-solution <<</d' "$rc" 2>/dev/null \
        || sed -i '/# >>> memory-solution >>>/,/# <<< memory-solution <<</d' "$rc"
      echo "  removed aliases from $rc"
    fi
  done

  echo "Done. Restart your shell or run 'source ~/.bashrc' (or ~/.zshrc) to stop using the aliases."
  exit 0
fi

# ---------------------------------------------------------------------------
# List available skills and scripts
# ---------------------------------------------------------------------------

SKILL_NAMES=()
while IFS= read -r d; do
  SKILL_NAMES+=("$(basename "$d")")
done < <(find "$SKILLS_SRC" -maxdepth 1 -type d ! -name "skills" | sort)

SCRIPT_NAMES=(
  "init_memory_bank.py"
  "init_vault.py"
  "promote.py"
  "sync_raw.py"
)

# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------

if [[ "$MODE" == "dry-run" ]]; then
  echo "=== Dry run — no changes will be made ==="
  echo
  echo "Skills install root: $SKILLS_INSTALL_ROOT"
  echo "Scripts location: $PROJECT_ROOT/scripts/"
  echo
  echo "Skills that would be rendered:"
  for s in "${SKILL_NAMES[@]}"; do
    echo "  - $s"
  done
  echo
  echo "Scripts that would be aliased:"
  for s in "${SCRIPT_NAMES[@]}"; do
    echo "  - $s"
  done
  echo
  echo "Aliases would be added to ~/.bashrc / ~/.zshrc."
  echo
  echo "Project configs that would be scaffolded:"
  scaffold_missing_configs
  exit 0
fi

# ---------------------------------------------------------------------------
# Interactive or auto mode
# ---------------------------------------------------------------------------

echo "=== memory-solution install ==="
echo
echo "Skills install root: $SKILLS_INSTALL_ROOT"
echo "Scripts location: $PROJECT_ROOT/scripts/"
echo

# ---------------------------------------------------------------------------
# Skills — pick which to install
# ---------------------------------------------------------------------------

echo "=== Skills ==="
echo "Select which skills to install. Skills not listed here are skipped."
echo

# In auto mode, install all skills; in interactive mode, ask per skill.
install_skills=()
skip_all_skills=false

for skill in "${SKILL_NAMES[@]}"; do
  if [[ "$MODE" == "auto" ]]; then
    install_skills+=("$skill")
  elif [[ "$skip_all_skills" == true ]]; then
    continue
  else
    echo "Install skill: $skill?"
    select answer in "Yes" "Skip" "Yes to all remaining" "Skip all remaining" "Quit"; do
      case "$REPLY" in
        1) install_skills+=("$skill"); break ;;
        2) break ;;
        3) install_skills+=("$skill"); skip_all_skills=true; break ;;
        4) skip_all_skills=true; break ;;
        5) echo "Aborted."; exit 0 ;;
      esac
    done
  fi
done

# ---------------------------------------------------------------------------
# Scripts — pick which to install and whether to add to PATH
# ---------------------------------------------------------------------------

echo
echo "=== Scripts ==="
echo "Select which scripts to install. Scripts are copied to"
echo "  $PROJECT_ROOT/scripts/"
echo "and can be added to your PATH via shell aliases."
echo

install_scripts=()
skip_all_scripts=false
add_scripts_to_path=false

for script in "${SCRIPT_NAMES[@]}"; do
  src="$SCRIPT_DIR/$script"
  [[ -f "$src" ]] || continue

  if [[ "$MODE" == "auto" ]]; then
    install_scripts+=("$script")
  elif [[ "$skip_all_scripts" == true ]]; then
    continue
  else
    echo "Install script: $script?"
    select answer in "Yes" "Skip" "Yes to all remaining" "Skip all remaining" "Quit"; do
      case "$REPLY" in
        1) install_scripts+=("$script"); break ;;
        2) break ;;
        3) install_scripts+=("$script"); skip_all_scripts=true; break ;;
        4) skip_all_scripts=true; break ;;
        5) echo "Aborted."; exit 0 ;;
      esac
    done
  fi
done

# Ask about PATH only if at least one script was selected.
if [[ ${#install_scripts[@]} -gt 0 ]]; then
  echo
  echo "Add aliases to your shell (~/.bashrc / ~/.zshrc) so these scripts"
  echo "are available as commands. Aliases point to
  $PROJECT_ROOT/scripts/<script>."
  if [[ "$MODE" == "auto" ]]; then
    add_scripts_to_path=true
    echo "  (auto: adding aliases)"
  else
    select answer in "Yes, add aliases" "No, install scripts only" "Quit"; do
      case "$REPLY" in
        1) add_scripts_to_path=true; break ;;
        2) add_scripts_to_path=false; break ;;
        3) echo "Aborted."; exit 0 ;;
      esac
    done
  fi
fi

# ---------------------------------------------------------------------------
# Do the installation
# ---------------------------------------------------------------------------

echo
echo "=== Installing ==="

# Project configs (scaffold any missing *.example.yaml → *.yaml).
echo
echo "=== Project configs ==="
scaffold_missing_configs

# Skills.
if [[ ${#install_skills[@]} -gt 0 ]]; then
  mkdir -p "$SKILLS_INSTALL_ROOT"
  python3 "$SCRIPT_DIR/render.py" \
    --skills-src "$SKILLS_SRC" \
    --dest "$SKILLS_INSTALL_ROOT" \
    2>&1 | grep -E '^  (rendered|would render)'
  echo "  skills installed to $SKILLS_INSTALL_ROOT"
else
  echo "  no skills selected — skipping"
fi

# Scripts.
if [[ ${#install_scripts[@]} -gt 0 ]]; then
  for script in "${install_scripts[@]}"; do
    echo "  added alias: $script"
  done
  echo "  scripts are aliased to $PROJECT_ROOT/scripts/"
else
  echo "  no scripts selected — skipping"
fi

# Aliases.
if [[ "$add_scripts_to_path" == true ]]; then
  add_aliases_to_shell
  echo "  aliases added to shell RC"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

echo
echo "=== Done ==="
if [[ ${#install_skills[@]} -gt 0 ]]; then
  echo "Skills: $SKILLS_INSTALL_ROOT/"
  echo "  Verify: ls $SKILLS_INSTALL_ROOT/"
  echo "  In pi: skills appear in the system prompt and as /skill:<name> commands."
fi
if [[ ${#install_scripts[@]} -gt 0 ]]; then
  echo "Scripts: $PROJECT_ROOT/scripts/"
  echo "  Available as commands after sourcing your shell RC (or restart shell)."
fi
if [[ "$add_scripts_to_path" != true && ${#install_scripts[@]} -gt 0 ]]; then
  echo "  Note: aliases were NOT added to your shell — scripts won't be available as commands."
  echo "  To add aliases later, re-run this script and choose 'Yes, add aliases'."
fi