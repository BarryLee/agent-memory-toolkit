# Architecture

## Goal

Give a coding agent a persistent working memory across projects and
sessions, where the human user is the gatekeeper of what becomes
"trusted" and what stays a "proposal".

## What the agent actually needs

The agent's fundamental problem is **context reconstruction** at the
start of every session. In principle, all the context it needs is in
its past sessions — read the session log and you can reconstruct
what was decided, what was tried, what was learned. In practice this
is intractable: session logs are large, the signal-to-noise is low,
and reading them all burns context budget that should go to the
current task.

Memory is the answer: a small, dense, *indexed* artifact that lets
the agent pull in the right context on demand rather than re-reading
everything.

## What we store, and why

Two kinds of information, often conflated:

- **Memory** — compressed, indexed. "There is a project called X.
  It uses Y. The relevant pattern is Z. Go read `[[foo]]` for the
  details." Memory is what makes the vault *findable*.
- **Knowledge** — detailed, specific, often long. "How Y actually
  works, with examples and gotchas." Knowledge is what makes the
  vault *useful* once you've found the right thing.

The two have to coexist. A vault of only memory is useless (just
indexes, no content). A vault of only knowledge is unfindable
(great content, no entry points). The `Learnings/` and `Patterns/`
categories hold knowledge; their `index.md` files hold the memory
over that knowledge.

## Trust zones

Three top-level directories, encoding a small state machine:

```
   ┌─────────┐  user promotes  ┌───────────┐
   │  Raw    │  (auto-sync)    │  Staging  │  user reviews   ┌──────────┐
   │ 00Raw   │  ───────────▶   │ 10Staging │  ─────────────▶  │ Curated  │
   │         │                 │           │                  │ 20Curated│
   │  read   │                 │  agent    │                  │  read    │
   │  only   │                 │  writes   │                  │  only    │
   │  to all │                 │           │                  │ to agent │
   └─────────┘                 └───────────┘                  └──────────┘
```

The states correspond to *trust*:

- `00Raw/` — untrusted. It's a mirror of project sources. The agent
  can read but must never cite it as memory.
- `10Staging/` — proposed. The agent writes here freely. The user
  hasn't blessed it; the agent shouldn't lean on it as ground
  truth when answering questions.
- `20Curated/` — trusted. The user is the only writer. The agent
  reads freely and treats it as authoritative.

The promotion step is **deliberately manual**. The user opens the
file in Obsidian, reads it, edits if needed, and copies it to
`20Curated/`. This gate is the whole point of the system: it
prevents the agent's bad days from poisoning its memory.

## Categories

The staging area is split into a fixed set of *first-level*
categories. The set is configurable via
`scripts/config/staging-categories.yaml`; the defaults are:

- `Projects/` — one short summary per project the agent has
  worked on. Cross-project pointer only; project-local detail
  goes in the project's memory bank.
- `Learnings/` — knowledge. "How X works", "What Y actually
  means", "Background on Z". Detailed.
- `Patterns/` — techniques. "When you need X, do Y". Terse.
  The split from `Learnings/` is *applicability*: a pattern
  is something you'd *do*; a learning is something you'd
  *know*.
- `Rules/` — rules the user has explicitly stated. The agent
  cannot promote a rule on its own — promotion is the user
  saying "yes, this rule is in effect."
- `TODO/` — cross-project TODOs only. Per-project work
  belongs in the project's memory bank.
- `People/` — one file per person mentioned in sessions.
  Plain working memory; not a review.
- `Events/` — meetings, conferences, incidents. Time-bounded
  and self-contained.

Each category has a `_guides.md` (purpose, what belongs, template,
naming rules) and an `index.md` (one-line summary of every entry
with a wikilink). The agent must read `_guides.md` before writing
a new note in a category, and update `index.md` after writing.

## Project memory banks

Each project the agent works in has its own
`memory-bank/` directory — a 5-file working-memory set
(`projectBrief`, `activeContext`, `progress`, `systemPatterns`,
`techContext`). On disk, `memory-bank/` is a symlink to
`10Staging/Projects/<slug>/memory-bank/` in the vault, so:

- The agent reads and writes the bank via `memory-bank/` from the
  project root, just like a normal folder.
- The user can browse and edit the same files from Obsidian, with
  full wikilink / search / graph support.
- Both views always see the same bytes — there is no sync step.

The bank is for *project-local* working memory. The vault is for
*cross-project* memory. Decision guide:

- Useful in any project? → vault.
- Useful only here? → bank.

When in doubt: bank first, promote to vault later if it proves
reusable.

## Active context

`10Staging/ActiveContext.md` is the *hot* memory. It is the file
the agent should read first when picking up a task ("what is the
focus right now?") and the file it should update whenever the
focus changes.

Discipline:

- Keep it short (~20 lines max).
- As soon as a topic is no longer the focus, summarize the outcome
  into the appropriate category note and trim it from active
  context.
- Don't let it become a journal. It's a TODO list with a sense of
  urgency, not a log.

## The agent's workflow

A typical session:

1. Load the project bank's `projectBrief.md` and `activeContext.md`
   to know what this project is and what's in focus.
2. If the work touches cross-project knowledge, grep the vault
   (`memory-vault-search`).
3. If the work references something from a prior session that isn't
   in the vault, search sessions (`search-sessions`).
4. Do the work.
5. Update `activeContext.md` and any affected bank files.
6. If reusable knowledge emerged, write a note in the vault
   (`update-memory-vault`).
7. If a new pattern/rule was established, write it in the vault.
8. If a TODO is unblocked or a milestone was reached, update
   `progress.md` (bank) and `TODO/` (vault if cross-project).

The user reviews vault notes asynchronously and promotes them to
`20Curated/`.

## What this design intentionally does *not* do

- **No automatic promotion.** Trust promotion is always manual.
- **No global search index (yet).** Grep is fast enough at this
  scale; vector search is a P1.
- **No agent-initiated promotion of rules.** Rules are
  user-stated; the agent can propose, not enact.
- **No cross-vault sync.** The vault is local; if you have
  multiple machines, the vault is one of them and rsync handles
  the rest.
- **No version control of the vault.** `00Raw/` is already a
  copy of version-controlled sources; `20Curated/` is the user's
  curated space (use Obsidian Sync or git if you want history);
  `10Staging/` is a draft board, history is not critical.
