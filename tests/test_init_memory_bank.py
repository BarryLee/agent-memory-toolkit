"""Integration tests for `scripts/init_memory_bank.py`.

Runs the script as a subprocess against a temp vault + project root.
See `test_init_vault.py` for why paths are `.resolve()`-d (macOS
`/tmp` -> `/private/tmp` symlink).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "init_memory_bank.py"

BANK_FILE_NAMES = [
    "projectBrief.md",
    "activeContext.md",
    "progress.md",
    "systemPatterns.md",
    "techContext.md",
]


def run_init_bank(
    vault_root: Path, project_root: Path, *extra: str, scaffold: bool = True
) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable, str(SCRIPT),
        "--vault-root", str(vault_root),
        "--project-root", str(project_root),
    ]
    if scaffold:
        cmd.append("--scaffold")
    return subprocess.run(
        [*cmd, *extra],
        check=False,
        capture_output=True,
        text=True,
    )


def _resolved_vault(tmp_path: Path) -> Path:
    p = tmp_path / "vault"
    p.mkdir(exist_ok=True)
    return p.resolve()


def _resolved_project(tmp_path: Path, name: str = "my-project") -> Path:
    p = tmp_path / name
    p.mkdir(exist_ok=True)
    return p.resolve()


# --- the 5 bank files -------------------------------------------------------


def test_creates_all_five_bank_files(tmp_path):
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path)
    result = run_init_bank(vault, project)
    assert result.returncode == 0, result.stderr
    bank = vault / "10Staging" / "Projects" / "my-project" / "memory-bank"
    for name in BANK_FILE_NAMES:
        assert (bank / name).is_file(), f"missing {name}"


def test_bank_files_have_template_content(tmp_path):
    """A spot-check that template content (not just empty files) was written."""
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path)
    result = run_init_bank(vault, project)
    assert result.returncode == 0, result.stderr
    bank = vault / "10Staging" / "Projects" / "my-project" / "memory-bank"
    brief = (bank / "projectBrief.md").read_text()
    assert brief.startswith("# Project Brief")
    assert "Project Brief" in brief
    # No leftover placeholders in any of the bank files.
    for name in BANK_FILE_NAMES:
        text = (bank / name).read_text()
        assert "{{" not in text, f"unrendered placeholder in {name}: {text!r}"


# --- the symlink -------------------------------------------------------------


def test_creates_symlink_in_project_root(tmp_path):
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path)
    result = run_init_bank(vault, project)
    assert result.returncode == 0, result.stderr

    link = project / "memory-bank"
    assert link.is_symlink(), f"{link} should be a symlink"
    target = os.readlink(link)
    expected_target = (vault / "10Staging" / "Projects" / "my-project" / "memory-bank").resolve()
    assert Path(target).resolve() == expected_target


def test_symlink_target_via_bank_file_works(tmp_path):
    """Reading the project-side symlink should yield the same bytes as
    reading the vault-side file directly."""
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path)
    result = run_init_bank(vault, project)
    assert result.returncode == 0, result.stderr

    via_symlink = (project / "memory-bank" / "projectBrief.md").read_text()
    direct = (vault / "10Staging" / "Projects" / "my-project" / "memory-bank" / "projectBrief.md").read_text()
    assert via_symlink == direct


# --- scope: the cross-project note is NOT this script's job -----------------


def test_does_not_create_project_note(tmp_path):
    """The cross-project summary note at 10Staging/<cat>/<slug>.md is a
    Projects-category file. It is created by the `update-memory-vault`
    skill (per the Projects guide), NOT by this script. Locking that
    boundary in as a test."""
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path)
    result = run_init_bank(vault, project)
    assert result.returncode == 0, result.stderr
    project_note = vault / "10Staging" / "Projects" / "my-project.md"
    assert not project_note.exists(), f"project note must not be created; found: {project_note}"


# --- idempotency -------------------------------------------------------------


def test_idempotent_does_not_overwrite_existing_files(tmp_path):
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path)
    r1 = run_init_bank(vault, project)
    assert r1.returncode == 0, r1.stderr
    brief = vault / "10Staging" / "Projects" / "my-project" / "memory-bank" / "projectBrief.md"
    brief.write_text("# tampered\n")

    r2 = run_init_bank(vault, project)
    assert r2.returncode == 0, r2.stderr
    assert brief.read_text() == "# tampered\n"


def test_idempotent_reports_existing_and_correct_symlink(tmp_path):
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path)
    r1 = run_init_bank(vault, project)
    assert r1.returncode == 0, r1.stderr

    r2 = run_init_bank(vault, project)
    assert r2.returncode == 0, r2.stderr
    # All 5 files should be reported as already existing.
    for name in BANK_FILE_NAMES:
        assert f"exists  10Staging/Projects/my-project/memory-bank/{name}" in r2.stdout
    # The symlink should be reported as already correct.
    assert "symlink already correct" in r2.stdout


# --- flags -------------------------------------------------------------------


def test_name_flag_overrides_project_slug(tmp_path):
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path, name="actual-dir-name")
    result = run_init_bank(vault, project, "--name", "custom-slug")
    assert result.returncode == 0, result.stderr
    assert (
        vault / "10Staging" / "Projects" / "custom-slug" / "memory-bank" / "projectBrief.md"
    ).is_file()
    # And the project-side symlink should point to the custom slug.
    link = project / "memory-bank"
    expected = (vault / "10Staging" / "Projects" / "custom-slug" / "memory-bank").resolve()
    assert Path(os.readlink(link)).resolve() == expected


def test_category_flag_changes_bank_location(tmp_path):
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path)
    result = run_init_bank(vault, project, "--category", "Projects")
    assert result.returncode == 0, result.stderr
    assert (vault / "10Staging" / "Projects" / "my-project" / "memory-bank" / "projectBrief.md").is_file()


# --- default behavior (no --scaffold) -------------------------------------------


def test_default_creates_only_dir_and_symlink(tmp_path):
    """By default the script only creates the vault-side directory and the
    project-side symlink — no template files are written unless --scaffold
    is passed. This makes the script safe to re-run without overwriting
    user-created bank files."""
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path)
    result = run_init_bank(vault, project, scaffold=False)
    assert result.returncode == 0, result.stderr
    bank = vault / "10Staging" / "Projects" / "my-project" / "memory-bank"
    # Vault-side directory was created.
    assert bank.is_dir(), f"vault bank dir should exist: {bank}"
    # Project-side symlink was created.
    link = project / "memory-bank"
    assert link.is_symlink(), f"symlink should exist: {link}"
    # But the 5 template files were NOT created.
    for name in BANK_FILE_NAMES:
        assert not (bank / name).exists(), f"{name} should not exist without --scaffold"


# --- error paths -------------------------------------------------------------


def test_dies_if_project_root_does_not_exist(tmp_path):
    vault = _resolved_vault(tmp_path)
    bogus = tmp_path / "does-not-exist"
    result = run_init_bank(vault, bogus)
    assert result.returncode != 0
    assert "project root does not exist" in result.stderr


def test_dies_if_existing_non_symlink_blocks_link(tmp_path):
    """If `<project>/memory-bank` exists as a regular file/dir, the script
    must refuse rather than overwrite."""
    vault = _resolved_vault(tmp_path)
    project = _resolved_project(tmp_path)
    (project / "memory-bank").write_text("not a symlink")
    result = run_init_bank(vault, project)
    assert result.returncode != 0
    assert "exists and is not a symlink" in result.stderr
    assert (project / "memory-bank").read_text() == "not a symlink"
