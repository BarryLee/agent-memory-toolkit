# TODO

Known gaps and follow-up work for the memory-solution. Items are
roughly ordered by priority.

## Promote shortcut (P1)

Today, promoting a note from `10Staging/` to `20Curated/` is
manual: open the file in Obsidian, copy it to the matching path
under `20Curated/`. This is fine, but a one-keybind shortcut would
be nice for the common case.

Options to evaluate:

- Obsidian's "Quick switcher + custom command" plugin.
- A Hammerspoon / Karabiner / Raycast hotkey that runs a small
  Python script (`promote.py`, not yet written) to do the
  file-system move.
- Obsidian URI handler with a small wrapper script.

**Decision pending:** pick the option that does not require
installing a heavy plugin. Whatever we choose, the underlying
operation should be a single Python script that takes a
`10Staging/<category>/<note>.md` path and copies it to
`20Curated/<category>/<note>.md` (preserving the relative
category).

## Vector search over the vault (P1)

The current `memory-vault-search` skill does grep. For larger
vaults, semantic search helps. Sketch:

- Build a small embedding index over `20Curated/` and `10Staging/`
  on each sync, with weights:
  - `20Curated/` — full weight (trusted).
  - `10Staging/` — half weight (proposal).
  - `00Raw/` — quarter weight (raw source; not memory).
- Expose a `vault-search` CLI that the skill calls.
- Decision: which vector store? Candidates: sqlite-vec (cheap,
  local, no extra service), chromadb (heavier, more features).

Blocked on: vault growing large enough that grep misses. Probably
~6 months out.

## Pi branching for memory work (P1)

The user wants the agent to do memory work (writing vault notes)
in a branched pi conversation, not the main line, so the main
context isn't polluted with file writes. Open question: does pi
have a CLI equivalent of Claude Code's `/fork` for branching the
current session?

If yes, the `update-memory-vault` skill should instruct the agent
to do exactly that before writing. If no, we either:

- Run memory writes inline (status quo, with a brief context cost).
- Write a small pi extension that implements a "do this in a
  branch and write the result back" pattern.

**Action:** research pi's SDK + branching commands. See
`~/.local/share/mise/installs/node/24.16.0/lib/node_modules/@earendil-works/pi-coding-agent/docs/sdk.md`
and `tui.md` for what is available. Also, use web search to investigate.

## `promote` CLI (P1)

The Python script backing the promote shortcut above. Will be
written when we pick a hotkey mechanism. Behavior: take a path
under `10Staging/`, copy it to `20Curated/`, preserving the
relative `10Staging/<category>/<note>` → `20Curated/<category>/<note>`
shape. Idempotent (refuse to overwrite a curated file unless
`--force`). Optionally delete the staging copy (`--delete`, off
by default — staging notes can be useful to keep around).

## Offline session summarizing and memory extraction

The current workflow relies on manually or agent proactively triggering the skills in session. An alternative approach is to have an agent inspect offline session logs and update the memory bank and memory vault according to their respective rules (e.g. have the agent referring to the skills).

## Git / history of curated (P3)

`20Curated/` is a hand-curated space. If the user wants history,
they can either:

- Use Obsidian Sync (closed-source, paid).
- Make the vault a git repo and commit curated changes
  explicitly.
- Use a separate dotfile-style backup.

Out of scope for the scripts; document the trade-off in the
README if/when the user wants it.

## Skill description tuning (P3)

The skill descriptions in `SKILL.md` frontmatter are critical
for pi to load them at the right time. They will need to be
tuned based on observed behavior — which skills get loaded
unnecessarily, which ones miss obvious cases. Plan: revisit
after a few weeks of real use.
