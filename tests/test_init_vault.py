"""Integration tests for `scripts/init_vault.py`.

These run the real script as a subprocess against a temp vault root
and inspect the files it produces. The vault path is `.resolve()`-d
before being handed to the script to side-step macOS's `/tmp` ->
`/private/tmp` symlink, which would otherwise break the
`path.relative_to(...)` calls inside the script's `info()` output.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "init_vault.py"


def run_init_vault(vault_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--vault-root", str(vault_root), *extra],
        check=False,
        capture_output=True,
        text=True,
    )


def _resolved_vault(tmp_path: Path) -> Path:
    """Return a fully-resolved vault path under the pytest temp dir.

    Resolving avoids macOS's `/tmp` -> `/private/tmp` symlink, which
    otherwise breaks `path.relative_to(...)` in the script.
    """
    p = tmp_path / "vault"
    p.mkdir(exist_ok=True)
    return p.resolve()


# --- root files --------------------------------------------------------------


def test_creates_root_files(tmp_path):
    vault = _resolved_vault(tmp_path)
    result = run_init_vault(vault)
    assert result.returncode == 0, result.stderr
    staging = vault / "10Staging"
    assert (staging / "AGENTS.md").is_file()
    assert (staging / "ActiveContext.md").is_file()
    assert (staging / "AboutUser.md").is_file()


def test_agents_md_renders_categories_list(tmp_path):
    vault = _resolved_vault(tmp_path)
    result = run_init_vault(vault)
    assert result.returncode == 0, result.stderr
    agents = (vault / "10Staging" / "AGENTS.md").read_text()
    assert "## Categories at a glance" in agents
    # The bundled example has 7 categories; check at least one.
    assert "- `10Staging/Projects/` — see `10Staging/Projects/_guides.md`." in agents
    assert "- `10Staging/Learnings/` — see `10Staging/Learnings/_guides.md`." in agents
    # Placeholder must have been substituted.
    assert "{{" not in agents
    assert "categories_list" not in agents


def test_category_index_renders_category_name(tmp_path):
    vault = _resolved_vault(tmp_path)
    result = run_init_vault(vault)
    assert result.returncode == 0, result.stderr
    index = (vault / "10Staging" / "Projects" / "index.md").read_text()
    assert index.startswith("# Projects — index")
    assert "{{" not in index
    assert "{{category}}" not in index


def test_active_context_template_supports_multiple_tasks(tmp_path):
    """The active-context template explicitly says several recent, active tasks
    can coexist. This locks in the wording change from "current task"."""
    vault = _resolved_vault(tmp_path)
    result = run_init_vault(vault)
    assert result.returncode == 0, result.stderr
    text = (vault / "10Staging" / "ActiveContext.md").read_text()
    assert "several" in text
    assert "active" in text
    # Should NOT have the old "current task" framing.
    assert "current task" not in text


# --- categories --------------------------------------------------------------


def test_creates_all_bundled_categories(tmp_path):
    vault = _resolved_vault(tmp_path)
    result = run_init_vault(vault)
    assert result.returncode == 0, result.stderr
    staging = vault / "10Staging"
    for cat in ("Projects", "Learnings", "Patterns", "Rules", "TODO", "People", "Events"):
        assert (staging / cat / "_guides.md").is_file(), f"missing {cat}/_guides.md"
        assert (staging / cat / "index.md").is_file(), f"missing {cat}/index.md"


def test_guides_md_content_matches_categories_config(tmp_path):
    """Each category's `_guides.md` body comes from staging-categories.yaml.

    The body starts with YAML frontmatter (--- description: ... ---), then
    the guide header.
    """
    vault = _resolved_vault(tmp_path)
    result = run_init_vault(vault)
    assert result.returncode == 0, result.stderr
    projects_guide = (vault / "10Staging" / "Projects" / "_guides.md").read_text()
    # The bundled example starts with frontmatter, then the guide header.
    assert projects_guide.startswith("---")
    assert "# Projects — guide" in projects_guide
    # Frontmatter must include a description field.
    assert "description:" in projects_guide


# --- curated root ------------------------------------------------------------


def test_creates_curated_root_files_and_dirs(tmp_path):
    vault = _resolved_vault(tmp_path)
    result = run_init_vault(vault)
    assert result.returncode == 0, result.stderr
    curated = vault / "20Curated"
    assert (curated / "ActiveContext.md").is_file()
    assert (curated / "AboutUser.md").is_file()
    for cat in ("Projects", "Learnings", "Patterns", "Rules", "TODO", "People", "Events"):
        assert (curated / cat).is_dir(), f"missing {CURATED}/{cat}/"


CURATED = "20Curated"


# --- idempotency & --force ---------------------------------------------------


def test_idempotent_does_not_overwrite_existing(tmp_path):
    vault = _resolved_vault(tmp_path)
    r1 = run_init_vault(vault)
    assert r1.returncode == 0, r1.stderr
    agents = vault / "10Staging" / "AGENTS.md"
    original = agents.read_text()
    # Modify the file so we can detect if it was overwritten.
    agents.write_text("# tampered\n")

    r2 = run_init_vault(vault)
    assert r2.returncode == 0, r2.stderr
    # Without --force, the user's edit must be preserved.
    assert agents.read_text() == "# tampered\n"
    # Sanity: original content was different from "tampered".
    assert original != "# tampered\n"


def test_force_overwrites_root_files(tmp_path):
    vault = _resolved_vault(tmp_path)
    r1 = run_init_vault(vault)
    assert r1.returncode == 0, r1.stderr
    agents = vault / "10Staging" / "AGENTS.md"
    agents.write_text("# tampered\n")

    r2 = run_init_vault(vault, "--force")
    assert r2.returncode == 0, r2.stderr
    # With --force, the file should be reset to the template.
    assert agents.read_text() != "# tampered\n"
    assert "Vault Conventions" in agents.read_text()


def test_force_never_overwrites_index_md(tmp_path):
    """Per the script's contract, `index.md` is hand-maintained and
    `--force` must not touch it."""
    vault = _resolved_vault(tmp_path)
    r1 = run_init_vault(vault)
    assert r1.returncode == 0, r1.stderr
    idx = vault / "10Staging" / "Projects" / "index.md"
    idx.write_text("# tampered index\n")

    r2 = run_init_vault(vault, "--force")
    assert r2.returncode == 0, r2.stderr
    assert idx.read_text() == "# tampered index\n"
