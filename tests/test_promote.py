"""Tests for `scripts/promote.py`.

Tests call promote.main() directly, allowing os.system to be mocked.
main() returns True on success, so happy-path tests don't need to catch SystemExit.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add scripts/ to path so we can import the module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import promote


def _resolved_path(tmp_path: Path) -> Path:
    """Return a resolved path under the pytest temp dir.

    Resolving avoids macOS's /tmp -> /private/tmp symlink.
    """
    return tmp_path.resolve()


def _create_test_vault(tmp_path: Path) -> Path:
    """Create a minimal test vault with staging and curated dirs."""
    vault = _resolved_path(tmp_path)
    (vault / "10Staging" / "Projects").mkdir(parents=True, exist_ok=True)
    (vault / "20Curated" / "Projects").mkdir(parents=True, exist_ok=True)
    return vault


@pytest.fixture(autouse=True)
def mock_os_system(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock os.system to prevent Obsidian launches in all tests."""
    mock = MagicMock()
    monkeypatch.setattr("scripts.promote.os.system", mock)
    return mock


@pytest.fixture(autouse=True)
def preserve_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure sys.argv is restored after each test."""
    original_argv = sys.argv
    yield
    sys.argv = original_argv


# --- happy path ---------------------------------------------------------------


def test_copies_file_to_curated(tmp_path: Path, mock_os_system: MagicMock) -> None:
    """Basic case: copy a staging file to curated, preserving structure."""
    vault = _create_test_vault(tmp_path)
    staging_file = vault / "10Staging" / "Projects" / "test-note.md"
    staging_file.write_text("# Test Note\n\nContent here.")

    sys.argv = ["promote.py", str(staging_file)]
    result = promote.main()

    assert result is True
    curated_file = vault / "20Curated" / "Projects" / "test-note.md"
    assert curated_file.is_file(), "Curated file should exist"
    assert curated_file.read_text() == "# Test Note\n\nContent here."
    assert staging_file.is_file(), "Staging file should still exist"
    mock_os_system.assert_called_once()


def test_preserves_relative_category(tmp_path: Path, mock_os_system: MagicMock) -> None:
    """File in 10Staging/Learnings/foo.md should go to 20Curated/Learnings/foo.md."""
    vault = _create_test_vault(tmp_path)
    (vault / "10Staging" / "Learnings").mkdir(parents=True, exist_ok=True)

    staging_file = vault / "10Staging" / "Learnings" / "pattern.md"
    staging_file.write_text("# Learning\n\nSome learning.")

    sys.argv = ["promote.py", str(staging_file)]
    result = promote.main()

    assert result is True
    curated_file = vault / "20Curated" / "Learnings" / "pattern.md"
    assert curated_file.is_file()


def test_creates_destination_directory(tmp_path: Path, mock_os_system: MagicMock) -> None:
    """If the curated subdirectory doesn't exist, it should be created."""
    vault = _create_test_vault(tmp_path)
    (vault / "10Staging" / "Events").mkdir(parents=True, exist_ok=True)

    staging_file = vault / "10Staging" / "Events" / "meetup.md"
    staging_file.write_text("# Event\n\nA meetup.")

    sys.argv = ["promote.py", str(staging_file)]
    result = promote.main()

    assert result is True
    curated_file = vault / "20Curated" / "Events" / "meetup.md"
    assert curated_file.is_file()
    assert (vault / "20Curated" / "Events").is_dir()


# --- error cases --------------------------------------------------------------


def test_rejects_file_not_in_staging(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """File not under 10Staging/ should be rejected."""
    vault = _create_test_vault(tmp_path)

    other_file = vault / "somewhere-else.md"
    other_file.write_text("# Not staging")

    sys.argv = ["promote.py", str(other_file)]
    result = promote.main()

    assert result is False
    captured = capsys.readouterr()
    assert "not in 10Staging/" in captured.err


def test_rejects_nonexistent_file(capsys: pytest.CaptureFixture[str]) -> None:
    """Non-existent file should be rejected."""
    fake_file = Path("/nonexistent/path/does-not-exist.md")

    sys.argv = ["promote.py", str(fake_file)]
    result = promote.main()

    assert result is False
    captured = capsys.readouterr()
    assert "does not exist" in captured.err


def test_refuses_to_overwrite_without_force(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """If curated file already exists, should refuse without --force."""
    vault = _create_test_vault(tmp_path)

    staging_file = vault / "10Staging" / "Projects" / "existing.md"
    staging_file.write_text("# Staging version")

    curated_file = vault / "20Curated" / "Projects" / "existing.md"
    curated_file.write_text("# Curated version")

    sys.argv = ["promote.py", str(staging_file)]
    result = promote.main()

    assert result is False
    captured = capsys.readouterr()
    assert "already exists" in captured.err
    assert curated_file.read_text() == "# Curated version"


def test_force_overwrites_existing(tmp_path: Path, mock_os_system: MagicMock) -> None:
    """With --force, should overwrite existing curated file."""
    vault = _create_test_vault(tmp_path)

    staging_file = vault / "10Staging" / "Projects" / "existing.md"
    staging_file.write_text("# New staging content")

    curated_file = vault / "20Curated" / "Projects" / "existing.md"
    curated_file.write_text("# Old curated content")

    sys.argv = ["promote.py", str(staging_file), "--force"]
    result = promote.main()

    assert result is True
    assert curated_file.read_text() == "# New staging content"


# --- --delete option ----------------------------------------------------------


def test_delete_removes_staging_file(tmp_path: Path, mock_os_system: MagicMock) -> None:
    """With --delete, the staging file should be removed after copy."""
    vault = _create_test_vault(tmp_path)

    staging_file = vault / "10Staging" / "Projects" / "to-delete.md"
    staging_file.write_text("# Will be deleted")

    sys.argv = ["promote.py", str(staging_file), "--delete"]
    result = promote.main()

    assert result is True
    assert not staging_file.exists(), "Staging file should be deleted"
    assert (vault / "20Curated" / "Projects" / "to-delete.md").is_file()


def test_delete_and_force_work_together(tmp_path: Path, mock_os_system: MagicMock) -> None:
    """--delete and --force can be combined."""
    vault = _create_test_vault(tmp_path)

    staging_file = vault / "10Staging" / "Projects" / "replace-and-delete.md"
    staging_file.write_text("# New content")

    curated_file = vault / "20Curated" / "Projects" / "replace-and-delete.md"
    curated_file.write_text("# Old content")

    sys.argv = ["promote.py", str(staging_file), "--delete", "--force"]
    result = promote.main()

    assert result is True
    assert not staging_file.exists()
    assert curated_file.read_text() == "# New content"


# --- --no-open option ---------------------------------------------------------


def test_no_open_skips_obsidian_launch(tmp_path: Path, mock_os_system: MagicMock) -> None:
    """With --no-open, os.system should not be called."""
    vault = _create_test_vault(tmp_path)

    staging_file = vault / "10Staging" / "Projects" / "no-open.md"
    staging_file.write_text("# No open test")

    sys.argv = ["promote.py", str(staging_file), "--no-open"]
    result = promote.main()

    assert result is True
    assert not mock_os_system.called, "os.system should not be called with --no-open"
    assert (vault / "20Curated" / "Projects" / "no-open.md").is_file()


def test_without_no_open_calls_obsidian(tmp_path: Path, mock_os_system: MagicMock) -> None:
    """Without --no-open, os.system should be called with obsidian:// URI."""
    vault = _create_test_vault(tmp_path)

    staging_file = vault / "10Staging" / "Projects" / "open-test.md"
    staging_file.write_text("# Open test")

    sys.argv = ["promote.py", str(staging_file)]
    result = promote.main()

    assert result is True
    mock_os_system.assert_called_once()
    call_args = mock_os_system.call_args[0][0]
    assert "obsidian://open?path=" in call_args
    assert "20Curated" in call_args


# --- path handling ------------------------------------------------------------


def test_handles_nested_category(tmp_path: Path, mock_os_system: MagicMock) -> None:
    """Deeply nested paths like 10Staging/A/B/C/file.md should work."""
    vault = _create_test_vault(tmp_path)

    nested_staging = vault / "10Staging" / "Projects" / "subfolder" / "nested.md"
    nested_staging.parent.mkdir(parents=True, exist_ok=True)
    nested_staging.write_text("# Nested")

    sys.argv = ["promote.py", str(nested_staging)]
    result = promote.main()

    assert result is True
    nested_curated = vault / "20Curated" / "Projects" / "subfolder" / "nested.md"
    assert nested_curated.is_file()
    assert nested_curated.read_text() == "# Nested"



