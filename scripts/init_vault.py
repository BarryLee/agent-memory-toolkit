#!/usr/bin/env python3
"""Initialize the Staging/Curated scaffold in the Obsidian vault.

Reads the canonical list of staging categories and their `_guides.md`
bodies from a YAML config (default: `scripts/config/staging-categories.yaml`),
and creates the matching directory tree, per-category `_guides.md` /
`index.md`, and root files (`AGENTS.md`, `ActiveContext.md`,
`AboutUser.md`).

The script is idempotent: it never overwrites an existing file, so you
can re-run it after pulling changes that added a new category. Use
`--force` to overwrite `_guides.md` and the root files (but never
`index.md` — that one is hand-maintained).

If the categories config is missing entirely, the script offers to copy
the bundled `staging-categories.example.yaml` to `staging-categories.yaml`
so the user has a starting point.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts._lib.config import load_yaml
    from scripts._lib.paths import (
        CURATED,
        DEFAULT_STAGING_CATEGORIES_CONFIG,
        STAGING,
        STAGING_ROOT_FILES,
        die,
        info,
        section,
        vault_root,
    )
else:
    from _lib.config import load_yaml
    from _lib.paths import (
        CURATED,
        DEFAULT_STAGING_CATEGORIES_CONFIG,
        STAGING,
        STAGING_ROOT_FILES,
        die,
        info,
        section,
        vault_root,
    )


EXAMPLE_PATH = DEFAULT_STAGING_CATEGORIES_CONFIG.with_name("staging-categories.example.yaml")


def _resolve_categories_config(
    config_path: Path,
    project_root: Path,
) -> tuple[Path, dict[str, str]]:
    """Return (resolved_config_path, {category_name: guide_body}).

    Falls back to the bundled example if neither the requested config nor
    the default exists. Errors if a config is requested explicitly but
    missing.
    """
    candidate = config_path
    if not candidate.exists():
        # Default wasn't created yet — fall back to the example so the
        # user can initialize a fresh vault with one command.
        if config_path == DEFAULT_STAGING_CATEGORIES_CONFIG and EXAMPLE_PATH.exists():
            info(
                f"no {config_path.name} yet — using bundled {EXAMPLE_PATH.name}. "
                f"Copy it to {config_path.name} to customize."
            )
            candidate = EXAMPLE_PATH
        else:
            die(
                f"categories config not found: {config_path}\n"
                f"Copy {EXAMPLE_PATH} to {config_path} and edit it."
            )

    raw = load_yaml(candidate)
    if not isinstance(raw, dict) or not raw:
        die(
            f"categories config {candidate} must be a non-empty mapping of "
            f"category-name -> guide-body. Got: {type(raw).__name__}"
        )

    # Normalize values: YAML may give us None, a str, or a multi-line block
    # scalar (which arrives as a str with trailing newlines preserved).
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not k:
            die(f"category key must be a non-empty string, got: {k!r}")
        if v is None:
            v = ""
        if not isinstance(v, str):
            die(f"category {k!r} body must be a string, got {type(v).__name__}")
        out[k] = v
    return candidate, out


def _vault_agents_md(categories: list[str]) -> str:
    cats = "\n".join(f"- `10Staging/{c}/` — see `10Staging/{c}/_guides.md`." for c in categories)
    return (
        "# Vault Conventions — for agents\n\n"
        "This vault is a structured memory store. Three top-level\n"
        "directories encode trust:\n\n"
        "- `00Raw/` — **READ ONLY to agents.** A read-only mirror of\n"
        "  project sources. Anything agent-written here is a bug.\n"
        "- `10Staging/` — **agent-written** drafts. Anything in here is a\n"
        "  *proposal* until the user reviews and promotes it.\n"
        "- `20Curated/` — **READ ONLY to agents.** Human-edited,\n"
        "  human-curated trusted memory. The user is the only one who\n"
        "  writes here. Treat the contents as ground truth when\n"
        "  answering from this vault.\n\n"
        "## Workflow\n\n"
        "1. To record something from a session, write to the appropriate\n"
        "   category under `10Staging/`. Read that category's `_guides.md`\n"
        "   first; it disambiguates the categories and gives you the\n"
        "   template.\n"
        "2. Update the category's `index.md` with a one-line summary of the\n"
        "   new note.\n"
        "3. For high-frequency context (what is the agent working on *right\n"
        "   now*?), update `10Staging/ActiveContext.md`. Keep it short and\n"
        "   current.\n"
        "4. The user promotes notes from `10Staging/` to `20Curated/`\n"
        "   after review. This is a manual step — do not assume a note is\n"
        "   trusted just because it's old.\n\n"
        "## Categories at a glance\n\n"
        f"{cats}\n\n"
        "## First principles\n\n"
        "- **Memory vs. knowledge**: this store holds both. Memory is\n"
        "  compressed — summaries and indexes. Knowledge is the\n"
        "  detailed layer below. Any category that admits detailed\n"
        "  notes still needs an `index.md` that summarizes its\n"
        "  contents — the categories list above tells you which\n"
        "  those are by reading their `_guides.md`.\n"
        "- **Cross-project only**: anything tied to a single project\n"
        "  belongs in that project's memory bank, not here. The\n"
        "  project-summary category in this vault exists to make the\n"
        "  vault discoverable from any project, not to hold project-\n"
        "  local detail.\n"
        "- **Optimize for the agent, not the human**: structure, indexes,\n"
        "  and consistent naming matter more than prose. The human\n"
        "  benefit is a side effect.\n"
    )


def _active_context_md() -> str:
    return (
        "# Active Context\n\n"
        "The agent's *hot* memory: what is in focus right now, the current\n"
        "task, recent decisions, and the next concrete step. This file\n"
        "should be short, time-stamped, and rotated aggressively — when a\n"
        "task is done, summarize the outcome into the appropriate category\n"
        "note under `10Staging/` and trim this file back to the new focus.\n\n"
        "## Current focus\n\n"
        "_None yet. Replace this with the active task on first use._\n\n"
        "## Recent decisions\n\n"
        "_None yet._\n\n"
        "## Next step\n\n"
        "_None yet._\n"
    )


def _about_user_md() -> str:
    return (
        "# About the User\n\n"
        "The agent's working model of the user. Keep this factual and\n"
        "narrow: things the agent would otherwise have to relearn at the\n"
        "start of every session. Avoid speculation.\n\n"
        "## Identity & context\n\n"
        "- Name: _unknown_\n"
        "- Time zone: _unknown_\n"
        "- Primary languages: _unknown_\n\n"
        "## Working style\n\n"
        "- _e.g. prefers terse answers, asks for trade-offs explicitly, ..._\n\n"
        "## Tooling\n\n"
        "- Editor / shell: _unknown_\n"
        "- Active projects: see the project-summary category under `10Staging/`.\n\n"
        "## Stated rules & preferences\n\n"
        "_Cross-reference into the rules category under `10Staging/` once\n"
        "those exist. Do not duplicate rule bodies here._\n"
    )


def _index_md(category: str) -> str:
    return (
        f"# {category} — index\n\n"
        f"One-line summaries of every entry in this category, with a\n"
        f"wikilink. **Update this file when you add or change an entry.**\n"
        f"It is the first thing an agent should read to know what's in\n"
        f"this category without walking the directory.\n\n"
        f"_Empty for now. Add a bullet of the form:_\n"
        f"\n```\n"
        f"- [[note-name]] — one-sentence summary.\n"
        f"```\n"
    )


def _ensure_file(path: Path, body: str, force: bool, *, allow_overwrite: bool) -> str:
    if path.exists():
        if force and allow_overwrite:
            path.write_text(body)
            return "overwrote"
        return "exists "
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--vault-root",
        type=Path,
        default=vault_root(),
        help="Obsidian vault root (default: ~/Documents/agentstuffs).",
    )
    parser.add_argument(
        "--categories-config",
        type=Path,
        default=DEFAULT_STAGING_CATEGORIES_CONFIG,
        help=(
            "YAML mapping of category name -> _guides.md body. "
            "Falls back to the bundled example if missing. "
            f"(default: {DEFAULT_STAGING_CATEGORIES_CONFIG})"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite _guides.md and root AGENTS.md/ActiveContext.md/AboutUser.md if they exist. Never overwrites index.md.",
    )
    args = parser.parse_args()

    config_path, categories = _resolve_categories_config(
        args.categories_config,
        project_root=Path(__file__).resolve().parent.parent,
    )
    category_names = list(categories.keys())

    staging = args.vault_root / STAGING
    curated = args.vault_root / CURATED

    section(f"Vault:        {args.vault_root}")
    section(f"Categories:   {config_path} ({len(category_names)} categories)")

    # Root files
    section("Staging root files")
    for name, body in (
        ("AGENTS.md", _vault_agents_md(category_names)),
        ("ActiveContext.md", _active_context_md()),
        ("AboutUser.md", _about_user_md()),
    ):
        status = _ensure_file(staging / name, body, args.force, allow_overwrite=True)
        info(f"{status} {STAGING}/{name}")

    # Category dirs
    section("Staging categories")
    for cat in category_names:
        cat_root = staging / cat
        cat_root.mkdir(parents=True, exist_ok=True)
        for name, body, allow_ow in (
            ("_guides.md", categories[cat], True),
            ("index.md", _index_md(cat), False),
        ):
            status = _ensure_file(cat_root / name, body, args.force, allow_overwrite=allow_ow)
            info(f"{status} {STAGING}/{cat}/{name}")
        (curated / cat).mkdir(parents=True, exist_ok=True)

    # Curated root
    section("Curated root")
    for cat in category_names:
        (curated / cat).mkdir(parents=True, exist_ok=True)
        info(f"created {CURATED}/{cat}/")
    for name in STAGING_ROOT_FILES:
        (curated / name).touch(exist_ok=True)
        info(f"touched  {CURATED}/{name}")

    section("Done")
    print("Next steps:")
    print(f"  1. Open the vault in Obsidian: open {args.vault_root}")
    print(f"  2. Run `python3 scripts/sync_raw.py` (with --apply) to mirror any project sources into 00Raw/.")
    print(f"  3. From any project root, run `python3 scripts/init_memory_bank.py` to scaffold a memory bank.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
