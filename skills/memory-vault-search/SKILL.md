---
name: memory-vault-search
description: Search the Obsidian memory vault for relevant notes. Use when the user asks a question that might be answered by a previously-recorded learning, pattern, rule, project summary, person, or event; or when you want to check what is already known before doing research. Reads 10Staging/ and 20Curated/ via grep/ripgrep on the active vault root (default ${VAULT_ROOT}).
---

# memory-vault-search

Search the memory vault for content relevant to a query. The vault
lives at `${VAULT_ROOT}`.

## When to use

- The user asks a "do we know anything about X?" question.
- You are about to do research and want to check what is already
  recorded (avoids re-discovering).
- You need to find a specific note by topic and don't remember the
  exact filename.
- You want to verify whether a proposed rule/pattern duplicates an
  existing one.

## When NOT to use

- You need **raw session content** (use `search-sessions` instead).
- You need to **read a specific file** (just use `read` on the path).
- You need to **search across the whole project tree** (this skill
  is scoped to the vault).

## Trust-aware search

The vault's three top-level dirs encode trust, and the skill should
respect it:

- `20Curated/` — trusted, promoted by the user. Prefer these in
  answers. Cite the path when you quote.
- `10Staging/` — proposed, agent-written, user not yet reviewed.
  Cite as "staging" or "draft". Do not treat as ground truth.
- `00Raw/` — read-only mirror of project sources. Useful for
  pointing at a project's docs, but not the agent's own memory.

When showing results, group by trust zone in the order
`20Curated → 10Staging → 00Raw` and label each group.

## How to search

Use `grep` (or `rg` if available — `rg` is faster on large trees).
Search **file body and filename**, in that order, and prefer filename
matches when the query is short:

```bash
# body search across the staged + curated portions of the vault
grep -ril "<query>" "${VAULT_ROOT}/20Curated" "${VAULT_ROOT}/10Staging"

# filename search
find "${VAULT_ROOT}/20Curated" "${VAULT_ROOT}/10Staging" -name "*<query>*"
```

If the user wants an exact phrase, quote it. If they want regex, use
`grep -E` or `rg -e`.

## Wikilink resolution

If the query is a wikilink target (e.g. the user wrote `[[foo]]` or
referred to a note by its bare name), look for:

- `**/foo.md` — exact filename match (highest priority)
- `**/*foo*` — substring filename match
- Body matches containing `[[foo]]` — backreferences

Return the resolved path so the user can open it directly in
Obsidian.

## Result format

For each result, return:

1. **Trust zone** (`20Curated/` / `10Staging/` / `00Raw/`).
2. **Path** relative to the vault root.
3. **One-line excerpt** of the matching line (with `...` for elision).
4. **Suggested next step** if obvious (e.g. "open in Obsidian",
   "read in full", "linked from `[[index]]`").

Cap the response at ~10 results. If more match, group by category
and show the most recent / most specific first.
