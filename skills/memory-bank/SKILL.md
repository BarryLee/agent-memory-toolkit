---
name: memory-bank
description: Read or update the project-local `memory-bank/` directory — a small set of structured markdown files that act as the project's persistent working memory. Use at the start of any non-trivial session to load project context, and after any meaningful change to record what was learned or decided. The bank is a fixed 5-file set; you should know each file's purpose and what to put in it.
---

# memory-bank

Each project the agent works in has a `memory-bank/` directory at its
root. From the agent's perspective, it is just a folder of markdown
files it can read and write like any other. Behind the scenes, the
folder is a symlink to a location inside the user's Obsidian vault,
so the user can browse and edit the same files from Obsidian with
full wikilink, search, and graph support.

The 5 files are a fixed set. Their purpose is to keep the agent's
working memory in a consistent, findable shape across projects, so
that "what is the project" / "what is the current focus" / "what
patterns apply" are always answerable from a known place.

## The 5 files

### `projectBrief.md`

The highest-level summary of the project: what it is, who it serves,
what success looks like. One paragraph, ideally. Read this first
when you start a session in a new project — it tells you whether
this is a project you should be working on at all.

What goes here:
- One-paragraph project description.
- Stakeholders / users.
- The success criterion in user-facing terms.

What does NOT go here:
- Implementation details (those go in `techContext.md`).
- Recent activity (that goes in `activeContext.md`).
- Project-local patterns (those go in `systemPatterns.md`).

### `activeContext.md`

The agent's *hot* memory for this project. What is being worked on
right now, recent decisions, and the next concrete step. Update
this aggressively — every time focus shifts, every time a decision
is made, every time the next step changes. This is the file the
agent will read first on the next session.

Keep it short. As soon as an item is no longer the current focus,
move it to `progress.md` (if it was a milestone) or to a category
note in the vault (if it's a reusable pattern or learning). The
file should rarely exceed ~20 lines.

### `progress.md`

An append-only log of dated milestones. Each entry is 1-3 lines:
date, what changed, why it mattered. Use ISO dates in headers so
sorting is stable.

What goes here:
- "Released v1.2 with X"
- "Migrated from Y to Z"
- "Decided to deprecate A in favor of B"

What does NOT go here:
- Free-form design notes (use `systemPatterns.md`).
- Detailed bug analysis (link to a vault note instead).
- Daily standup noise — milestones only.

### `systemPatterns.md`

Architecture and design conventions specific to this project. The
key word is *project-specific*: if a pattern applies across
projects, it belongs in the cross-project patterns category under
the vault and should be linked from here, not duplicated.

What goes here:
- Module boundaries and their rationale.
- Coding conventions unique to this project.
- "When adding X, do Y" rules that only make sense here.

What does NOT go here:
- Generic language/framework patterns (vault's cross-project
  patterns category).
- The full architecture spec (that's `00Raw/<project>/`).

### `techContext.md`

The toolchain quick-reference: languages, frameworks, build/test
commands, deployment, and the specific quirks an agent would
otherwise have to rediscover. The goal is "next session can start
working in 30 seconds".

What goes here:
- Languages, versions, key dependencies.
- Build / test / lint / format commands (copy-pastable).
- Deployment steps or a link to the runbook.
- Known toolchain quirks (e.g. "the dev container needs X env
  var").

What does NOT go here:
- Tutorials or "how to use language Y" content.
- Design rationale (that's `systemPatterns.md`).
- API docs (link out).

## How to use this skill

### Starting a session in a project

1. Read `projectBrief.md` — decide if this is a project you should
   be working in.
2. Read `activeContext.md` — pick up where the last session left
   off.
3. Skim `progress.md` for the last 1-2 entries — recent trajectory.
4. Skim `systemPatterns.md` and `techContext.md` only if the
   current task touches something they describe.

### During the session

- When focus changes → update `activeContext.md`.
- When you learn something that will be useful next time but isn't
  covered by the 5 files → update the appropriate file (or, for
  cross-project knowledge, write a note in the vault via
  `update-memory-vault` and link it from `systemPatterns.md` or
  `techContext.md`).
- When a milestone is reached → add a `## YYYY-MM-DD` entry to
  `progress.md` and trim `activeContext.md`.

### The "hot" discipline

The single most common failure mode is `activeContext.md` going
stale. The cure is to treat it like a TODO list: every time you
finish a unit of work, look at `activeContext.md` and ask "is the
focus still accurate?" If not, update it *before* you do anything
else. If the focus is done, summarize the outcome and clear it.

## Where the bank lives

- The bank itself is at `<project-root>/memory-bank/` from the
  agent's point of view.
- The folder is a symlink. The real files live in the user's
  Obsidian vault. Editing through the symlink and editing from
  Obsidian both work and stay in sync.
- If the symlink is missing or broken, treat it as a configuration
  problem: do not try to repair the symlink yourself, and do not
  invent a fallback path. Tell the user that the memory bank is
  not accessible in this project; they will handle the fix.

## Bank vs. vault

The bank is **project-scoped** working memory. The vault is
**cross-project** memory. Decision guide:

- Will this be useful when the user works on a *different* project?
  → Vault (`update-memory-vault`).
- Is this only meaningful for this project, even if briefly?
  → Bank.
- When in doubt: bank first, promote to vault later if it proves
  reusable.
