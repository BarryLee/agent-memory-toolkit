#!/usr/bin/env python3
"""Initialize a project-local `memory-bank` directory.

The bank is a small set of structured markdown files that act as the
project's working memory — what the project is, what is being worked on
right now, what patterns have emerged, and so on. Concretely it is a
5-file set (projectBrief, activeContext, progress, systemPatterns,
techContext) — see BANK_TEMPLATES below.

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
        STAGING,
        die,
        info,
        section,
        safe_project_name,
        staging_root,
    )
else:
    from _lib.paths import (
        STAGING,
        die,
        info,
        section,
        safe_project_name,
        staging_root,
    )


PROJECT_ROOT_HELP = (
    "Project root containing (or to contain) the memory-bank symlink. "
    "Defaults to $PWD. The directory name is also used as the project slug."
)
VAULT_ROOT_HELP = "Obsidian vault root. Defaults to ~/Documents/agentstuffs."


# The 5 canonical memory-bank files. Templates are deliberately short —
# they scaffold the shape, not the content. Agents/users will fill them
# in. The pattern itself (5 files, fixed names) is documented in the
# `memory-bank` skill's SKILL.md, which is the right place to look for
# "what is a memory bank and how do I use it" — not a README inside the
# bank (which would be duplicated in every project).
BANK_TEMPLATES: dict[str, str] = {
    "projectBrief.md": (
        "# Project Brief\n\n"
        "One-paragraph description of what this project is, who it serves, "
        "and what success looks like. Update this last; it is the highest-"
        "level summary and should be derivable from the other files.\n"
    ),
    "activeContext.md": (
        "# Active Context\n\n"
        "The current focus: what is being worked on right now, recent "
        "decisions, and the next concrete step. Keep this *short* and "
        "temporal — entries older than the current focus should move to "
        "progress.md.\n\n"
        "## Current focus\n\n"
        "- \n\n"
        "## Recent decisions\n\n"
        "- \n\n"
        "## Next step\n\n"
        "- \n"
    ),
    "progress.md": (
        "# Progress\n\n"
        "Append-only log of milestones and their dates. Keep entries short "
        "(1-3 lines). Use ISO dates in headers.\n\n"
        "## YYYY-MM-DD\n\n"
        "- \n"
    ),
    "systemPatterns.md": (
        "# System Patterns\n\n"
        "Architecture and design conventions specific to this project. "
        "Cross-project patterns belong in the curated vault under the "
        "cross-project patterns category, and should be linked from here "
        "rather than duplicated.\n\n"
        "## Architecture\n\n"
        "- \n\n"
        "## Conventions\n\n"
        "- \n\n"
        "## Project-local patterns\n\n"
        "- \n"
    ),
    "techContext.md": (
        "# Tech Context\n\n"
        "Languages, frameworks, build/test commands, deployment, and the "
        "specific toolchain quirks that an agent would otherwise have to "
        "rediscover. Keep this as a *quick-reference*, not a tutorial.\n\n"
        "## Stack\n\n"
        "- \n\n"
        "## Build & test\n\n"
        "```bash\n# example\n```\n\n"
        "## Quirks\n\n"
        "- \n"
    ),
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


def _init_vault_bank(vault_dir: Path, project_slug: str, project_root: Path, category: str) -> None:
    vault_dir.mkdir(parents=True, exist_ok=True)
    # No README in the bank. The pattern is documented in the
    # `memory-bank` skill's SKILL.md; duplicating a README into every
    # project is busywork.
    for name, body in BANK_TEMPLATES.items():
        target = vault_dir / name
        if target.exists():
            info(f"exists  {target.relative_to(staging_root().parent)}")
            continue
        target.write_text(body)
        info(f"created {target.relative_to(staging_root().parent)}")

    # Also ensure there's a 10Staging/<category>/<slug>.md summary note
    # that links to the bank. This is the cross-project pointer.
    project_note = staging_root() / category / f"{project_slug}.md"
    project_note.parent.mkdir(parents=True, exist_ok=True)
    if not project_note.exists():
        body = (
            f"# {project_slug}\n\n"
            f"## Source\n\n"
            f"`{project_root}`\n\n"
            f"## Memory bank\n\n"
            f"See [[{project_slug}/memory-bank/projectBrief]]. The 5-file "
            f"bank lives under "
            f"`10Staging/{category}/{project_slug}/memory-bank/` and is "
            f"symlinked into the project root as `memory-bank`.\n\n"
            f"## Summary\n\n"
            f"_Add a 1-3 sentence description of what this project is._\n"
        )
        project_note.write_text(body)
        info(f"created {project_note.relative_to(staging_root().parent)}")


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
            "Staging category under which to create the project's memory "
            "bank directory and summary note. Defaults to 'Projects' — "
            "override if you renamed that category in your "
            "staging-categories.yaml."
        ),
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    if not project_root.exists():
        die(f"project root does not exist: {project_root}")

    slug = args.name or _project_slug(project_root)
    category = args.category
    vault_dir = (args.vault_root / STAGING / category / slug / "memory-bank").resolve()
    section(f"Project: {project_root}")
    section(f"Slug:    {slug}")
    section(f"Vault bank: {vault_dir}")

    _init_vault_bank(vault_dir, slug, project_root, category)
    _link_project_side(vault_dir, project_root)
    section("Done")
    print("  Open the bank in Obsidian at:")
    print(f"    <vault>/{STAGING}/{category}/{slug}/memory-bank/projectBrief.md")
    print("  Or in your editor at:")
    print(f"    {project_root}/memory-bank/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
