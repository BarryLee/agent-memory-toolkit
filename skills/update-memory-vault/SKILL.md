---
name: update-memory-vault
description: Record something from the current session into the staging area of the Obsidian memory vault. Use when the user asks to remember, note, save, or capture something; when a session produced a non-trivial learning, pattern, rule, person, event, or project update; or when active context is stale. Reads the active vault root (default ${VAULT_ROOT}) and decides which category fits the new material.
---

# update-memory-vault

This skill is the **single entry point** for writing to the memory vault.
The vault lives at `${VAULT_ROOT}`. It has three top-level trust zones:

- `00Raw/` — read-only mirror of project sources. **Never write here.**
- `10Staging/` — agent-written drafts. This is where *you* write.
- `20Curated/` — user-curated trusted memory. **READ ONLY to agents**;
  the human user is the one who writes here.

When called, read `${VAULT_ROOT}/10Staging/AGENTS.md` first if you have
not already in this session — it has the workflow rules. Then decide
which category the new material belongs in.

## What "current task memory" means

`${VAULT_ROOT}/10Staging/ActiveContext.md` is the **hot** memory. Treat
it as the agent's scratchpad for *what is happening right now*. After
any non-trivial task, check it: if it is stale or missing the current
focus, update it. Keep it short — entries older than the current focus
should be summarized into a category note and trimmed from active
context.

## Step 1 — choose the category

The canonical categories live under `${VAULT_ROOT}/10Staging/`. The
list is configured by the user (it can grow, shrink, or be renamed),
so do **not** rely on any fixed list you have seen before. Instead:

1. Read `${VAULT_ROOT}/10Staging/AGENTS.md`. It contains a "Categories
   at a glance" section that is the authoritative current list.
2. For each candidate category, read its
   `${VAULT_ROOT}/10Staging/<category>/_guides.md`. The guide
   disambiguates the categories and tells you what does and doesn't
   belong.
3. The filesystem is the source of truth — if a category exists on
   disk that isn't in AGENTS.md, trust the disk.

If none of the existing categories fit, you may create a **new**
category directory. Match the existing naming style (capitalized,
no separators), and add an entry to `AGENTS.md` under "Categories
at a glance" so the next agent can find it. Don't proliferate
categories — one good new category is fine, several are a sign you
should re-think.

## Step 2 — read the category's `_guides.md` and follow it

For the category you chose, read
`${VAULT_ROOT}/10Staging/<category>/_guides.md` *in full* before
writing. It contains:

- **What goes here** vs **what does NOT go here** — the boundaries of
  the category.
- **Template** — the exact skeleton for a note in that category.
- **Naming & file layout** — file naming convention, when to use a
  subdirectory.
- **Don't forget** — typically: update the category's `index.md`.

Use the template as the starting structure. You can extend sections
the template doesn't have, but don't drop the ones it does have —
they are what make the category uniform.

## Step 3 — write the file

File-level rules that apply on top of the category template:

- **One concept per file** when reasonable. A 200-line file is harder
  to index than five 40-line files; a one-line file is a one-line
  file.
- **File name = the concept**, in kebab-case. Match the convention
  the category's `_guides.md` specifies (most categories use
  kebab-case; some use the project name as-is).
- If a topic spans multiple files (e.g. a project with sub-systems),
  create a subdirectory following whatever the category's
  `_guides.md` recommends.

## Step 4 — maintain active context

After writing, ask: does `${VAULT_ROOT}/10Staging/ActiveContext.md`
need an update?

- New project, new ongoing task → write the focus there.
- Task completed → trim the entry, summarize the outcome into the
  appropriate category note, and rotate.

`ActiveContext.md` should rarely exceed ~20 lines. If it does, you've
stopped treating it as hot memory.

## Step 5 — maintain the index

For the category you wrote to, edit its `index.md` and add a
one-line entry with a wikilink:

```diff
- _Empty for now._
+ - [[my-new-note]] — one-sentence summary.
```

This is the most-skipped step and the most important — an unindexed
note is an unfindable note.

## What this skill does NOT do

- **Promote** notes to `20Curated/`. That is a manual user step.
- **Edit `00Raw/`.** That is a read-only mirror of project sources.
- **Touch the project's local memory bank.** That is the
  `memory-bank` skill's job.

## Inputs the user might give you

The user can call this skill with no arguments (you infer from
context) or with hints like:

- "remember that ..."
- "save this to <category>"
- "log a cross-project TODO for X"
- "add a rule: never Y"
- "create a person note for Z"
- "update active context — we're now working on W"

If the user names a category that doesn't exist in the current vault
layout, double-check `AGENTS.md` and the filesystem before
correcting them — they may have renamed or removed a category
recently, and the new name is the right one.

Treat explicit hints as constraints on the category and tone, not as
a script to follow literally.
