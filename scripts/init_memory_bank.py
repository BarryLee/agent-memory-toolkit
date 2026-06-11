#!/usr/bin/env python3
"""Initialize a project-local `memory-bank` directory.

The bank is a small set of structured markdown files that act as the
project's working memory — what the project is, what is being worked on
right now, what patterns have emerged, and so on. Concretely it is a
5-file set (projectBrief, activeContext, progress, systemPatterns,
techContext). The bodies of those files are loaded from markdown
template files in `scripts/config/templates/bank/` (see
`_lib/templates.py` for the `{{name}}` placeholder syntax).

Layout on disk:

  <project-root>/
    memory-bank/          <-- symlink to the vault location below
  <vault>/10Staging/<category>/<project-slug>/memory-bank/
    projectBrief.md
    activeContext.md
    progress.md
    systemPatterns.md
    techContext.md

The directory is named `memory-bank/` (no leading dot) so that
Obsidian's file explorer shows it by default — the leading-dot
convention is a Unix / agent-tool idiom that Obsidian does not honor.
The vault stores the actual files; the project-side entry is a
symlink so the agent and your editor see the same bytes as Obsidian
does, and so both stay in sync without a copy step.

This script creates only the 5 bank files and the project-side
symlink. The cross-project summary note that lives at
`10Staging/<category>/<slug>.md` is a `Projects`-category file and is
created by the `update-memory-vault` skill (following the `Projects`
category guide) — not by this script.

The script is idempotent on the 5 bank files: existing files are
never overwritten, only the symlink is re-created if missing. Run it
once per project (or whenever you want to re-establish the link).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts._lib.paths import (
        BANK_TEMPLATES_DIR,
        STAGING,
        die,
        info,
        section,
        safe_project_name,
        staging_root,
    )
    from scripts._lib import templates
else:
    from _lib.paths import (
        BANK_TEMPLATES_DIR,
        STAGING,
        die,
        info,
        section,
        safe_project_name,
        staging_root,
    )
    from _lib import templates


PROJECT_ROOT_HELP = (
    "Project root containing (or to contain) the memory-bank symlink. "
    "Defaults to $PWD. The directory name is also used as the project slug."
)
VAULT_ROOT_HELP = "Obsidian vault root. Defaults to ~/Documents/agentstuffs."


# The 5 canonical memory-bank files. Their *names* are fixed (the
# `memory-bank` skill's SKILL.md documents the pattern; an Obsidian
# user should be able to find these by name) — only the *bodies* are
# externalized to templates. The script never creates a README inside
# the bank; the pattern is documented in the skill.
_BANK_TEMPLATE_FILES: list[tuple[str, str]] = [
    # (output filename in bank, template filename under scripts/config/templates/bank/).
    # Output names are camelCase (the on-disk bank files); templates
    # are kebab-case to match the vault template convention.
    ("projectBrief.md", "project-brief.md.tmpl"),
    ("activeContext.md", "active-context.md.tmpl"),
    ("progress.md", "progress.md.tmpl"),
    ("systemPatterns.md", "system-patterns.md.tmpl"),
    ("techContext.md", "tech-context.md.tmpl"),
]


def _load_bank_templates() -> dict[str, str]:
    """Load the 5 bank templates. None of them have placeholders.

    Returns a dict keyed by file basename (e.g. `"projectBrief.md"`).
    """
    return {
        out_name: templates.load(BANK_TEMPLATES_DIR / tmpl_name)
        for out_name, tmpl_name in _BANK_TEMPLATE_FILES
    }


def _project_slug(project_root: Path) -> str:
    """Derive a safe slug for `project_root`.

    Convention: the slug is simply the directory name — it matches the
    name of the directory under which `memory-bank` is being created, so
    the bank's path and its slug always agree. If the user has a different
    name in mind (e.g. they want the vault to call the project
    `example-app` even though the directory is `example_app`), they can
    pass `--name` explicitly.
    """
    return safe_project_name(project_root.name)


def _init_vault_bank(vault_dir: Path, vault_root: Path, bank_tmpls: dict[str, str]) -> None:
    """Write the 5 bank files into `vault_dir`.

    `vault_root` is the actual vault root for this run (resolved),
    used to build the relative path printed by `info()`. We do NOT
    use `staging_root().parent` here because that helper reads the
    `MEMORY_VAULT_ROOT` env var (or defaults to
    `~/Documents/agentstuffs`) and ignores `--vault-root`.
    """
    vault_dir.mkdir(parents=True, exist_ok=True)
    # No README in the bank. The pattern is documented in the
    # `memory-bank` skill's SKILL.md; duplicating a README into every
    # project is busywork.
    for out_name in bank_tmpls:
        target = vault_dir / out_name
        if target.exists():
            info(f"exists  {target.relative_to(vault_root)}")
            continue
        target.write_text(bank_tmpls[out_name])
        info(f"created {target.relative_to(vault_root)}")


def _link_project_side(vault_dir: Path, project_root: Path) -> None:
    link = project_root / "memory-bank"
    if link.is_symlink():
        target = os.readlink(link)
        if Path(target).resolve() == vault_dir:
            info(f"symlink already correct: {link} -> {target}")
            return
        die(
            f"{link} is a symlink to {target!r}, not {vault_dir}. "
            f"Remove it manually if you want to retarget."
        )
    if link.exists():
        die(
            f"{link} exists and is not a symlink. Move or delete it before "
            f"running this script so the symlink can be created."
        )
    os.symlink(vault_dir, link)
    info(f"symlinked {link} -> {vault_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help=PROJECT_ROOT_HELP)
    parser.add_argument("--vault-root", type=Path, default=staging_root().parent, help=VAULT_ROOT_HELP)
    parser.add_argument(
        "--name",
        help="Override the project slug. Default: the directory name of --project-root (or $PWD).",
    )
    parser.add_argument(
        "--category",
        default="Projects",
        help=(
            "Staging category under which the memory bank directory "
            "lives. Defaults to 'Projects' — override if you renamed "
            "that category in your staging-categories.yaml. (The cross-"
            "project summary note is not created by this script; it is a "
            "Projects-category file written by the `update-memory-vault` "
            "skill.)"
        ),
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    if not project_root.exists():
        die(f"project root does not exist: {project_root}")

    slug = args.name or _project_slug(project_root)
    category = args.category
    vault_root = args.vault_root.resolve()
    vault_dir = vault_root / STAGING / category / slug / "memory-bank"
    section(f"Project: {project_root}")
    section(f"Slug:    {slug}")
    section(f"Vault bank: {vault_dir}")

    _init_vault_bank(vault_dir, vault_root, _load_bank_templates())
    _link_project_side(vault_dir, project_root)
    section("Done")
    print("  Open the bank in Obsidian at:")
    print(f"    <vault>/{STAGING}/{category}/{slug}/memory-bank/projectBrief.md")
    print("  Or in your editor at:")
    print(f"    {project_root}/memory-bank/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
