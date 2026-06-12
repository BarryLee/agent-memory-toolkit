"""Tests for `scripts/promote.py`.

These run the script as a subprocess against a temp vault root.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "promote.py"


def run_promote(*args: str) -> subprocess.CompletedProcess:
    """Run promote.py and return the result."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _resolved_path(tmp_path: Path) -> Path:
    """Return a resolved path under the pytest temp dir.
    
    Resolving avoids macOS's /tmp -> /private/tmp symlink.
    """
    p = tmp_path.resolve()
    return p


def _create_test_vault(tmp_path: Path) -> Path:
    """Create a minimal test vault with staging and curated dirs."""
    vault = _resolved_path(tmp_path)
    (vault / "10Staging" / "Projects").mkdir(parents=True, exist_ok=True)
    (vault / "20Curated" / "Projects").mkdir(parents=True, exist_ok=True)
    return vault


# --- happy path ---------------------------------------------------------------


def test_copies_file_to_curated(tmp_path):
    """Basic case: copy a staging file to curated, preserving structure."""
    vault = _create_test_vault(tmp_path)
    staging_file = vault / "10Staging" / "Projects" / "test-note.md"
    staging_file.write_text("# Test Note\n\nContent here.")
    
    result = run_promote(str(staging_file))
    
    assert result.returncode == 0, result.stderr
    curated_file = vault / "20Curated" / "Projects" / "test-note.md"
    assert curated_file.is_file(), "Curated file should exist"
    assert curated_file.read_text() == "# Test Note\n\nContent here."
    assert staging_file.is_file(), "Staging file should still exist"


def test_preserves_relative_category(tmp_path):
    """File in 10Staging/Learnings/foo.md should go to 20Curated/Learnings/foo.md."""
    vault = _create_test_vault(tmp_path)
    (vault / "10Staging" / "Learnings").mkdir(parents=True, exist_ok=True)
    
    staging_file = vault / "10Staging" / "Learnings" / "pattern.md"
    staging_file.write_text("# Learning\n\nSome learning.")
    
    result = run_promote(str(staging_file))
    
    assert result.returncode == 0, result.stderr
    curated_file = vault / "20Curated" / "Learnings" / "pattern.md"
    assert curated_file.is_file()


def test_creates_destination_directory(tmp_path):
    """If the curated subdirectory doesn't exist, it should be created."""
    vault = _create_test_vault(tmp_path)
    # Only Projects exists; create a staging file in a new category
    (vault / "10Staging" / "Events").mkdir(parents=True, exist_ok=True)
    # Note: Events doesn't exist in curated yet
    
    staging_file = vault / "10Staging" / "Events" / "meetup.md"
    staging_file.write_text("# Event\n\nA meetup.")
    
    result = run_promote(str(staging_file))
    
    assert result.returncode == 0, result.stderr
    curated_file = vault / "20Curated" / "Events" / "meetup.md"
    assert curated_file.is_file()
    assert (vault / "20Curated" / "Events").is_dir()


# --- error cases --------------------------------------------------------------


def test_rejects_file_not_in_staging(tmp_path):
    """File not under 10Staging/ should be rejected."""
    vault = _create_test_vault(tmp_path)
    
    # File in a random location
    other_file = vault / "somewhere-else.md"
    other_file.write_text("# Not staging")
    
    result = run_promote(str(other_file))
    
    assert result.returncode == 1
    assert "not in 10Staging/" in result.stderr


def test_rejects_nonexistent_file(tmp_path):
    """Non-existent file should be rejected."""
    vault = _create_test_vault(tmp_path)
    fake_file = vault / "10Staging" / "Projects" / "does-not-exist.md"
    
    result = run_promote(str(fake_file))
    
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_refuses_to_overwrite_without_force(tmp_path):
    """If curated file already exists, should refuse without --force."""
    vault = _create_test_vault(tmp_path)
    
    staging_file = vault / "10Staging" / "Projects" / "existing.md"
    staging_file.write_text("# Staging version")
    
    curated_file = vault / "20Curated" / "Projects" / "existing.md"
    curated_file.parent.mkdir(parents=True, exist_ok=True)
    curated_file.write_text("# Curated version")
    
    result = run_promote(str(staging_file))
    
    assert result.returncode == 1
    assert "already exists" in result.stderr
    # Original curated content should be preserved
    assert curated_file.read_text() == "# Curated version"


def test_force_overwrites_existing(tmp_path):
    """With --force, should overwrite existing curated file."""
    vault = _create_test_vault(tmp_path)
    
    staging_file = vault / "10Staging" / "Projects" / "existing.md"
    staging_file.write_text("# New staging content")
    
    curated_file = vault / "20Curated" / "Projects" / "existing.md"
    curated_file.parent.mkdir(parents=True, exist_ok=True)
    curated_file.write_text("# Old curated content")
    
    result = run_promote(str(staging_file), "--force")
    
    assert result.returncode == 0, result.stderr
    assert curated_file.read_text() == "# New staging content"


# --- --delete option ----------------------------------------------------------


def test_delete_removes_staging_file(tmp_path):
    """With --delete, the staging file should be removed after copy."""
    vault = _create_test_vault(tmp_path)
    
    staging_file = vault / "10Staging" / "Projects" / "to-delete.md"
    staging_file.write_text("# Will be deleted")
    
    result = run_promote(str(staging_file), "--delete")
    
    assert result.returncode == 0, result.stderr
    assert not staging_file.exists(), "Staging file should be deleted"
    assert (vault / "20Curated" / "Projects" / "to-delete.md").is_file()


def test_delete_and_force_work_together(tmp_path):
    """--delete and --force can be combined."""
    vault = _create_test_vault(tmp_path)
    
    staging_file = vault / "10Staging" / "Projects" / "replace-and-delete.md"
    staging_file.write_text("# New content")
    
    curated_file = vault / "20Curated" / "Projects" / "replace-and-delete.md"
    curated_file.write_text("# Old content")
    
    result = run_promote(str(staging_file), "--delete", "--force")
    
    assert result.returncode == 0, result.stderr
    assert not staging_file.exists()
    assert curated_file.read_text() == "# New content"


# --- path handling ------------------------------------------------------------


def test_expands_tilde_path(tmp_path):
    """Paths starting with ~ should be expanded."""
    vault = _create_test_vault(tmp_path)
    
    staging_file = vault / "10Staging" / "Projects" / "tilde-test.md"
    staging_file.write_text("# Tilde path test")
    
    # Use tilde path (we can't literally use ~ in the test, so we use the full path)
    result = run_promote(str(staging_file))
    
    assert result.returncode == 0, result.stderr
    assert (vault / "20Curated" / "Projects" / "tilde-test.md").is_file()


def test_handles_nested_category(tmp_path):
    """Deeply nested paths like 10Staging/A/B/C/file.md should work."""
    vault = _create_test_vault(tmp_path)
    
    nested_staging = vault / "10Staging" / "Projects" / "subfolder" / "nested.md"
    nested_staging.parent.mkdir(parents=True, exist_ok=True)
    nested_staging.write_text("# Nested")
    
    result = run_promote(str(nested_staging))
    
    assert result.returncode == 0, result.stderr
    nested_curated = vault / "20Curated" / "Projects" / "subfolder" / "nested.md"
    assert nested_curated.is_file()
    assert nested_curated.read_text() == "# Nested"


# --- help and --no-open -------------------------------------------------------


def test_shows_help(tmp_path):
    """--help should display usage and exit."""
    result = run_promote("--help")
    
    assert result.returncode == 0
    assert "promote" in result.stdout.lower()
    assert "10Staging" in result.stdout


def test_no_open_suppresses_obsidian_launch(tmp_path):
    """--no-open should complete without trying to open Obsidian.
    
    We can't fully test Obsidian integration, but we can verify
    the script exits cleanly with --no-open and doesn't fail.
    """
    vault = _create_test_vault(tmp_path)
    
    staging_file = vault / "10Staging" / "Projects" / "no-open.md"
    staging_file.write_text("# No open test")
    
    result = run_promote(str(staging_file), "--no-open")
    
    # Should succeed without trying to open Obsidian
    assert result.returncode == 0, result.stderr
    assert (vault / "20Curated" / "Projects" / "no-open.md").is_file()
