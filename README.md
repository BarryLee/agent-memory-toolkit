# memory-solution

An Obsidian-vault-based memory system for coding agents. The agent
writes to a staging area; the human curates; a curated copy becomes
the trusted memory bank. The vault lives at `~/Documents/agentstuffs`
by default.

## First principles

1. **Two things live in this vault: memory and knowledge.** Memory is
   compressed — summaries and indexes. Knowledge is the detailed
   layer below. Both are useful; the discipline is keeping the
   memory layer honest.
2. **The agent's memory problem is context reconstruction.** Reading
   every past session is theoretically enough to rebuild any
   context, but at our scale that is intractable. So we curate.
3. **Memory is for the agent.** The human benefit is a side effect.
   Optimize for structure, indexes, and consistency over prose.
4. **Only cross-project material lives here.** Project-local detail
   belongs in that project's memory bank. Vault `Projects/` holds
   only short summaries + indexes.

## Layout

```
~/Documents/agentstuffs/
├── 00Raw/          # read-only mirror of project sources (auto-synced)
├── 10Staging/      # agent-written, human-curated drafts
│   ├── AGENTS.md          # workflow rules + categories list (read first)
│   ├── ActiveContext.md   # hot memory — keep short, update often
│   ├── AboutUser.md       # working model of the user
│   ├── Projects/          # one short summary per project
│   ├── Learnings/         # knowledge: how X works
│   ├── Patterns/          # techniques: when you need X, do Y
│   ├── Rules/             # explicit user-stated rules
│   ├── TODO/              # cross-project TODOs
│   ├── People/            # one file per person
│   └── Events/            # meetings, conferences, incidents
└── 20Curated/      # human-curated, agent-read-only trusted memory
    └── (mirrors the staging layout, populated by the user)
```

## Quickstart

```bash
# 1. Initialize the vault scaffold (idempotent).
python3 scripts/init_vault.py

# 2. (Optional) Mirror project sources into 00Raw/.
#    Edit scripts/config/sync.yaml first, then:
python3 scripts/sync_raw.py            # dry-run
python3 scripts/sync_raw.py --apply    # actually copy

# 3. From any project, set up a Cline-style memory bank.
cd ~/code/myapp
python3 ~/agent-workspaces/memory-solution/scripts/init_memory_bank.py
# creates a 5-file memory-bank/ in the vault, symlinked into the project

# 4. Install the skills so the agent can find them.
bash ~/agent-workspaces/memory-solution/scripts/install.sh
```

## Day-to-day

- **Recording session content**: the agent uses the
  `update-memory-vault` skill. It reads the category's `_guides.md`
  for the format and writes to `10Staging/`.
- **Searching the vault**: the `memory-vault-search` skill does a
  trust-aware grep across `20Curated/` and `10Staging/`.
- **Searching past sessions**: the `search-sessions` skill wraps
  `agentsview session search`.
- **Maintaining the project bank**: the `memory-bank` skill is
  loaded automatically when the agent sees a `memory-bank/`
  directory in the project.
- **Promoting a note**: the user opens the vault in Obsidian,
  reviews the file under `10Staging/`, and copies it to the matching
  location under `20Curated/`. This is a manual, deliberate step.

## Where the configuration lives

- `scripts/config/sync.yaml` — what to mirror into `00Raw/`
  (per-project `source` + `target`, with `include` / `exclude`).
- `scripts/config/staging-categories.yaml` — the list of staging
  categories and their `_guides.md` bodies. Add or rename categories
  here, then re-run `init_vault.py` to apply.
- `scripts/config/install.yaml` — values substituted into skills
  during `install.sh` (currently just `vault_root`). Override at
  install time with `MEMORY_VAULT_ROOT=...`.

See `docs/architecture.md` for a deeper write-up, and
`docs/TODO.md` for known gaps.
