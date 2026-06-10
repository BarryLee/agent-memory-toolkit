---
name: search-sessions
description: Search the user's past agent sessions (Claude Code, Codex, pi, etc.) for content via the local agentsview CLI. Use when the user asks "didn't we talk about X before", when you need to look up something the agent did or said in a previous session, when you want to find a specific error/tool invocation/project context, or when the memory vault doesn't have the answer and the original session might.
---

# search-sessions

Search the local `agentsview` session archive for content from past
agent sessions. Use this when the answer is more likely in raw
session history than in the curated memory vault.

## When to use

- The user references something from a previous session: "we
  discussed X last week", "the bug we hit in Y", "the approach you
  suggested for Z".
- You need to find a specific **tool invocation**, **error message**,
  or **shell command** the agent ran before.
- The memory vault doesn't have it, but a prior conversation probably
  does.
- The user asks "what projects have we worked on" or "summarize the
  last session about X".

## When NOT to use

- The answer is in the memory vault (use `memory-vault-search` first
  — it is faster and curated).
- The user wants you to **run a new session** or take a new action
  (this is read-only search).
- The user wants the live state of an in-progress session (use
  `agentsview session watch <id>` directly — out of scope for this
  skill).

## Tool: `agentsview session search`

The CLI ships with the `agentsview` binary. The relevant command
group is `session`, and the search command is:

```
agentsview session search <pattern> [flags]
```

Full options:

- `--regex` — treat pattern as RE2 regex.
- `--fts` — tokenized FTS5 search; messages-only. Fastest on large
  archives, but skips tool input/result.
- `--in messages,tool_input,tool_result` — restrict to message
  bodies, tool inputs, or tool results. Default is all three.
- `--exclude-system` — drop system messages.
- `--project <name>` — narrow to one project (matches agentsview's
  `project` field, which is the directory name slug).
- `--agent <name>` — narrow to one agent harness (e.g. `pi`,
  `claude`, `codex`).
- `--date <YYYY-MM-DD>` / `--date-from` / `--date-to` — date range.
- `--active-since <RFC3339>` — sessions with activity since.
- `--limit N` — default 50, max 500.
- `--cursor N` — pagination from a prior result.
- `--include-one-shot` / `--include-automated` /
  `--include-children` — opt back into session types that are
  excluded by default.

The default (substring, no flags) is usually the right starting
point. Use `--fts` only when substring is too noisy and you can
phrase the query as a few keywords.

## Practical recipes

```bash
# Find anything the user or agent said about a topic
agentsview session search "memory vault" --limit 10

# Find a specific error/tool result
agentsview session search "ENOENT" --in tool_result --limit 20

# Restrict to one project (note: agentsview slugs the project name)
agentsview session search "sync_raw" --project memory_solution

# Regex for "any sentence that mentions the word foo in any form"
agentsview session search "\bfoo\w*\b" --regex --limit 10

# Full-text keyword search (fastest)
agentsview session search "rsync itemize openrsync" --fts --limit 10
```

## After you have a hit

The result includes `session_id`, `project`, `ordinal` (the message
position), `location` (`message` / `tool_input` / `tool_result`),
`tool_name`, and a ~120-char snippet. To read the surrounding
context:

```bash
# Read messages around a hit (find the session first, then page)
agentsview session list --project <slug> --date-from YYYY-MM-DD --limit 5
agentsview session messages <session_id> --from <ordinal-3> --limit 10
```

If you need the **raw transcript** (e.g. the user wants to see the
exact tool call), use `agentsview session export <id>` (local
only) or the HTTP `/api/v1/sessions/{id}/export` endpoint for
HTML/markdown.

## Pagination

If `--limit` truncates results, the response has a `next_cursor`.
Pass it back with `--cursor` to get the next page. Stop paginating
once you have enough to answer.

## What you do with the result

- Summarize the relevant finding in 1-3 lines.
- Quote the snippet (the agent masks secrets automatically; do not
  request `--reveal`).
- If the user wants to take action based on the finding, suggest the
  next concrete step (open the file, re-run the command, etc.).
- Do not bulk-export full sessions unless asked — the snippets are
  usually enough and exports can be large.

## Server vs local

`agentsview` may be running as a daemon or opening the local SQLite
archive directly. Both work; the search results are the same. If
neither is running, the CLI starts a one-shot local search
automatically. No setup is needed beyond having `agentsview`
installed (verify with `agentsview --version`).
