"""Shared path and config utilities for the memory-solution scripts.

Keep this module dependency-free (only stdlib) so scripts can be run directly
with `python3 scripts/...` without any venv setup.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable


# Default locations; overridable via env var MEMORY_VAULT_ROOT.
DEFAULT_VAULT_ROOT = Path(os.environ.get("MEMORY_VAULT_ROOT", "~/Documents/agentstuffs")).expanduser()

# Top-level subdirs of the vault.
RAW = "00Raw"
STAGING = "10Staging"
CURATED = "20Curated"

# Default path to the staging-categories config (relative to the project).
DEFAULT_STAGING_CATEGORIES_CONFIG = Path(__file__).resolve().parent.parent / "config" / "staging-categories.yaml"

# Markdown template directory. Templates are plain `.md.tmpl` files
# with `{{name}}` placeholders; see `_lib/templates.py` for the syntax
# and the render/load helpers.
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "config" / "templates"
VAULT_TEMPLATES_DIR = TEMPLATES_DIR / "vault"
BANK_TEMPLATES_DIR = TEMPLATES_DIR / "bank"

# Hard-coded fallback used only if the YAML config is missing or malformed.
# Keep this in sync with scripts/config/staging-categories.example.yaml.
DEFAULT_STAGING_CATEGORIES: dict[str, str] = {}

# Files that live at staging/curated root (not under a category).
STAGING_ROOT_FILES = [
    "ActiveContext.md",
    "AboutUser.md",
]


def vault_root() -> Path:
    """Return the configured vault root, ensuring it exists."""
    root = DEFAULT_VAULT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def staging_root() -> Path:
    p = vault_root() / STAGING
    p.mkdir(parents=True, exist_ok=True)
    return p


def curated_root() -> Path:
    p = vault_root() / CURATED
    p.mkdir(parents=True, exist_ok=True)
    return p


def raw_root() -> Path:
    p = vault_root() / RAW
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_under_vault(path: Path) -> bool:
    """True if `path` is inside the configured vault root."""
    try:
        path.resolve().relative_to(vault_root().resolve())
        return True
    except ValueError:
        return False


# Files and dirs to never touch when promoting or mirroring.
# - Obsidian config: do not sync into 00Raw, do not promote.
# - Git internals: never copy.
# - Hidden dotfiles: keep promotion strict.
SKIP_NAMES = {
    ".obsidian",
    ".git",
    ".DS_Store",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
}


def safe_project_name(name: str) -> str:
    """Slugify a project name so it works as a directory name.

    Rules: lowercase, replace any run of non-alphanumeric chars with a single
    hyphen, no leading/trailing hyphens.
    """
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if not s:
        raise ValueError(f"project name {name!r} slugifies to empty string")
    return s


def iter_md_files(root: Path) -> Iterable[Path]:
    """Yield markdown files under `root`, skipping junk dirs."""
    for path in sorted(root.rglob("*.md")):
        if any(part in SKIP_NAMES for part in path.parts):
            continue
        yield path


def die(msg: str, code: int = 1) -> None:
    """Print to stderr and exit with non-zero status."""
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def info(msg: str) -> None:
    print(f"  {msg}")


def section(title: str) -> None:
    print(f"\n=== {title} ===")
