# Promote Shortcut Setup (Obsidian Shell Commands)

This guide sets up a one-keybind shortcut to promote the currently-open note from `10Staging/` to `20Curated/`.

## Prerequisites

1. **Obsidian Shell Commands plugin** installed and enabled
   - Open Obsidian → Settings → Community plugins → Search "Shell Commands" → Install → Enable

2. **Script available on PATH or referenced by full path**
   - The script lives at: `~/agent-workspaces/memory-solution/scripts/promote.py`
   - Or: add it to your shell PATH

## Setup Steps

### 1. Add the Shell Command

1. Open Obsidian → Settings → **Shell Commands**
2. Click **New command**
3. Fill in:

   **Command alias** (what appears in command palette):
   ```
   Promote to Curated
   ```

   **Shell command**:
   ```
   python3 ~/agent-workspaces/memory-solution/scripts/promote.py {{file_path:absolute}}
   ```

   **Working directory** (optional, but useful):
   ```
   ~/agent-workspaces/memory-solution/scripts
   ```

4. Click **Create**
5. Create another command "Promote to Curated - force" for `python3 ~/agent-workspaces/memory-solution/scripts/promote.py --force {{file_path:absolute}}`

### 2. Assign a Hotkey (optional)

1. Open Obsidian → Settings → **Hotkeys**
2. Search for `Promote to Curated` (or the alias you chose)
3. Click the field and press your desired key combination
4. Suggested: `Cmd+Shift+P` (avoids conflict with `Cmd+P` for Quick Switcher)

### 3. Usage

1. Open any note in `10Staging/`
2. Press `Cmd+Shift+P` (or use `Cmd+P` then select `Promote to Curated`)
3. The note is copied to the matching path in `20Curated/` and opened in Obsidian

## Options

The script supports flags you can add to the shell command:

| Flag | Effect |
|------|--------|
| `--force` | Overwrite if destination exists |
| `--delete` | Delete staging copy after promoting (default: keep it) |
| `--no-open` | Don't open file in Obsidian after promoting |

Example with options:
```
python3 ~/agent-workspaces/memory-solution/scripts/promote.py {{file_path}} --force --delete
```

## Troubleshooting

**"File is not in 10Staging/" error**: The command only works for files under `10Staging/`. Make sure you're promoting from the right vault location.

**Script not found**: Verify the path to `promote.py` is correct. Use `ls ~/agent-workspaces/memory-solution/scripts/promote.py` to check.

**Hotkey conflicts**: If `Cmd+Shift+P` conflicts with something, pick another combo. Common alternatives: `Cmd+Ctrl+P`, `Cmd+Option+P`.

## File Context

The plugin provides `{{file_path}}` when a note is open. This is how Obsidian Shell Commands knows which file to promote — no clipboard or window-title scraping needed.
