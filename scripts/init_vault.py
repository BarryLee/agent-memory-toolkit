#!/usr/bin/env python3
"""Initialize the Staging/Curated scaffold in the Obsidian vault.

Reads the canonical list of staging categories and their `_guides.md`
bodies from a YAML config (default: `scripts/config/staging-categories.yaml`),
and creates the matching directory tree, per-category `_guides.md` /
`index.md`, and root files (`AGENTS.md`, `ActiveContext.md`,
`AboutUser.md`). The text bodies for the root files and the per-
category `index.md` are loaded from markdown template files in
`scripts/config/templates/vault/` (see `_lib/templates.py` for the
`{{name}}` placeholder syntax).

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
        VAULT_TEMPLATES_DIR,
        die,
        info,
        section,
        vault_root,
    )
    from scripts._lib import templates
else:
    from _lib.config import load_yaml
    from _lib.paths import (
        CURATED,
        DEFAULT_STAGING_CATEGORIES_CONFIG,
        STAGING,
        STAGING_ROOT_FILES,
        VAULT_TEMPLATES_DIR,
        die,
        info,
        section,
        vault_root,
    )
    from _lib import templates


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


def _load_vault_templates() -> dict[str, str]:
    """Load the four vault templates from `VAULT_TEMPLATES_DIR`.

    Returns a dict keyed by the destination root file (or `index_md`
    for the per-category index template). Each value is the raw
    template text; render with `templates.render(...)` at write time.
    """
    return {
        "agents_md": templates.load(VAULT_TEMPLATES_DIR / "agents.md.tmpl"),
        "active_context_md": templates.load(VAULT_TEMPLATES_DIR / "active-context.md.tmpl"),
        "about_user_md": templates.load(VAULT_TEMPLATES_DIR / "about-user.md.tmpl"),
        "index_md": templates.load(VAULT_TEMPLATES_DIR / "category-index.md.tmpl"),
    }


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

    # Build the categories list once, for the AGENTS.md placeholder.
    cats = "\n".join(
        f"- `10Staging/{c}/` — see `10Staging/{c}/_guides.md`."
        for c in category_names
    )

    vault_tmpls = _load_vault_templates()

    # Root files
    section("Staging root files")
    for name, body in (
        (
            "AGENTS.md",
            templates.render(vault_tmpls["agents_md"], {"categories_list": cats}),
        ),
        ("ActiveContext.md", templates.render(vault_tmpls["active_context_md"], {})),
        ("AboutUser.md", templates.render(vault_tmpls["about_user_md"], {})),
    ):
        status = _ensure_file(staging / name, body, args.force, allow_overwrite=True)
        info(f"{status} {STAGING}/{name}")

    # Category dirs
    section("Staging categories")
    for cat in category_names:
        cat_root = staging / cat
        cat_root.mkdir(parents=True, exist_ok=True)
        index_body = templates.render(vault_tmpls["index_md"], {"category": cat})
        for name, body, allow_ow in (
            ("_guides.md", categories[cat], True),
            ("index.md", index_body, False),
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
