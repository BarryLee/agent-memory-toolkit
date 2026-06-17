"""Integration tests for `scripts/sync_raw.py`.

These run the real script as a subprocess against a temp source tree
and a temp vault root. We use `.resolve()` on both to side-step macOS's
`/tmp` -> `/private/tmp` symlink, which would otherwise break the
`path.relative_to(...)` calls inside the script's `info()` output.

Each test uses a fresh source + vault to stay isolated. rsync is
required (it's used by the script for the actual copy step); it's
preinstalled on macOS and most Linux distros.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "sync_raw.py"


def _resolved(p: Path) -> Path:
    """Resolve a path to side-step macOS /tmp -> /private/tmp."""
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def _make_source_files(root: Path, *paths: str) -> None:
    """Create empty .md files at the given paths relative to `root`."""
    for rel in paths:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {rel}\n")


def _write_config(config_path: Path, vault_root: Path, source: Path, target: str,
                  include: list[str] | None = None, exclude: list[str] | None = None,
                  delete: bool = False) -> None:
    """Write a minimal sync.yaml pointing at the test source/vault."""
    import yaml as _yaml
    cfg: dict = {
        "vault_root": str(vault_root),
        "syncs": [
            {
                "source": str(source),
                "target": target,
                **({"include": include} if include is not None else {}),
                **({"exclude": exclude} if exclude is not None else {}),
                **({"delete": True} if delete else {}),
            }
        ],
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_yaml.safe_dump(cfg, sort_keys=False))


def run_sync(config: Path, vault_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(config), "--vault-root", str(vault_root), *extra],
        check=False,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Bug 1: UnboundLocalError on empty rels
# ---------------------------------------------------------------------------


def test_empty_rels_does_not_crash(tmp_path):
    """When no files match the include/exclude rules, the script must
    return cleanly instead of raising UnboundLocalError on `transferred`.
    """
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    # Source has zero .md files.
    _write_config(config, vault, source, target="x", include=["**/*.md"])
    result = run_sync(config, vault)
    assert result.returncode == 0, result.stderr
    assert "nothing to transfer" in result.stdout
    # Summary line should still print with the right (zeroed) numbers.
    assert "transferred/planned: 0" in result.stdout
    assert "removed/plan-remove: 0" in result.stdout
    assert "unchanged:           0" in result.stdout


def test_empty_rels_with_hard_excludes_only(tmp_path):
    """Even with files present (but all excluded by hard excludes),
    the script must not crash."""
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    # Only non-md content; hard-excluded dirs only.
    (source / "node_modules").mkdir()
    (source / "node_modules" / "x.md").write_text("# skip")
    (source / "README.txt").write_text("not markdown")

    _write_config(config, vault, source, target="x")
    result = run_sync(config, vault)
    assert result.returncode == 0, result.stderr
    assert "0 files match" in result.stdout


# ---------------------------------------------------------------------------
# Bug 2: target dir auto-creation
# ---------------------------------------------------------------------------


def test_creates_dest_dir_when_missing(tmp_path):
    """The script must create the 00Raw/<target>/ dir if it doesn't
    exist, in both dry-run and apply modes."""
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    _make_source_files(source, "README.md")
    target = "local/my-project"
    _write_config(config, vault, source, target=target, include=["**/*.md"])

    # Pre-condition: dest dir does not exist.
    dest = vault / "00Raw" / target
    assert not dest.exists()

    # Dry run: dest dir should still be created (so the rsync call
    # doesn't error out on a missing parent).
    result = run_sync(config, vault)
    assert result.returncode == 0, result.stderr
    assert dest.is_dir(), f"dry-run should still create {dest}"

    # Apply: the file lands at the expected dest.
    result_apply = run_sync(config, vault, "--apply")
    assert result_apply.returncode == 0, result_apply.stderr
    assert (dest / "README.md").is_file()


def test_creates_deeply_nested_dest(tmp_path):
    """Multi-segment targets like `code/example-app/sub` should also
    be created end-to-end."""
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    _make_source_files(source, "notes.md")
    target = "code/example-app/sub"
    _write_config(config, vault, source, target=target)

    result = run_sync(config, vault, "--apply")
    assert result.returncode == 0, result.stderr
    assert (vault / "00Raw" / target / "notes.md").is_file()


# ---------------------------------------------------------------------------
# Bug 3: per-file logging (dry-run shows destination paths)
# ---------------------------------------------------------------------------


def test_dry_run_prints_dest_path_for_each_file(tmp_path):
    """The per-file log should mention the destination path, in
    vault-relative form, so the user can see exactly where in the
    vault each file would land."""
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    _make_source_files(source, "README.md", "docs/notes.md", "deep/nested/file.md")
    target = "local/my-project"
    _write_config(config, vault, source, target=target, include=["**/*.md"])

    result = run_sync(config, vault)  # dry-run
    assert result.returncode == 0, result.stderr

    expected_paths = [
        "00Raw/local/my-project/README.md",
        "00Raw/local/my-project/docs/notes.md",
        "00Raw/local/my-project/deep/nested/file.md",
    ]
    for path in expected_paths:
        assert path in result.stdout, f"expected `{path}` in dry-run output:\n{result.stdout}"

    # The verb is "would create" in dry-run.
    assert "would create:" in result.stdout


def test_apply_uses_creating_verb(tmp_path):
    """In --apply mode, the per-file verb flips to "creating:"."""
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    _make_source_files(source, "a.md")
    _write_config(config, vault, source, target="t", include=["**/*.md"])

    result = run_sync(config, vault, "--apply")
    assert result.returncode == 0, result.stderr
    assert "creating:" in result.stdout
    assert "00Raw/t/a.md" in result.stdout


def test_no_op_files_listed_as_unchanged(tmp_path):
    """On a second run with no source changes, files are listed as
    no-op and the count summary reflects that."""
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    _make_source_files(source, "stable.md")
    _write_config(config, vault, source, target="t", include=["**/*.md"])

    # First run: copy the file.
    r1 = run_sync(config, vault, "--apply")
    assert r1.returncode == 0, r1.stderr

    # Second run: no changes — per-file log should be empty, summary
    # should show 0 transfers and 1 no-op.
    r2 = run_sync(config, vault)
    assert r2.returncode == 0, r2.stderr
    assert "planned transfers: 0" in r2.stdout
    assert "no-op entries: 1" in r2.stdout


# ---------------------------------------------------------------------------
# Bug 4: glob semantics (`*` doesn't cross `/`)
# ---------------------------------------------------------------------------


def test_single_star_include_does_not_match_subdirs(tmp_path):
    """A pattern like `*.md` (single-component `*`) must not pick up
    files in subdirectories — the user has to write `**/*.md` for
    that. This locks in the new gitignore-style semantics."""
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    _make_source_files(source, "README.md", "sub/nested.md")
    _write_config(config, vault, source, target="t", include=["*.md"])

    result = run_sync(config, vault, "--apply")
    assert result.returncode == 0, result.stderr
    # Only the root-level file lands; nested is excluded.
    assert (vault / "00Raw" / "t" / "README.md").is_file()
    assert not (vault / "00Raw" / "t" / "sub" / "nested.md").exists()
    assert "1 files match" in result.stdout


def test_double_star_include_catches_subdirs(tmp_path):
    """`**/*.md` should match files at any depth, including root."""
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    _make_source_files(source, "README.md", "sub/nested.md", "a/b/c/deep.md")
    _write_config(config, vault, source, target="t", include=["**/*.md"])

    result = run_sync(config, vault, "--apply")
    assert result.returncode == 0, result.stderr
    assert (vault / "00Raw" / "t" / "README.md").is_file()
    assert (vault / "00Raw" / "t" / "sub" / "nested.md").is_file()
    assert (vault / "00Raw" / "t" / "a" / "b" / "c" / "deep.md").is_file()


def test_hard_excludes_still_apply(tmp_path):
    """`.obsidian`, `node_modules`, etc. should still be excluded
    regardless of the include pattern."""
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    _make_source_files(source, "keep.md", ".obsidian/x.md", "node_modules/y.md", "__pycache__/z.md")
    _write_config(config, vault, source, target="t", include=["**/*.md"])

    result = run_sync(config, vault, "--apply")
    assert result.returncode == 0, result.stderr
    assert (vault / "00Raw" / "t" / "keep.md").is_file()
    assert not (vault / "00Raw" / "t" / ".obsidian").exists()
    assert not (vault / "00Raw" / "t" / "node_modules").exists()
    assert not (vault / "00Raw" / "t" / "__pycache__").exists()


# ---------------------------------------------------------------------------
# Example config — the bundled patterns must work end-to-end
# ---------------------------------------------------------------------------


def test_example_config_patterns_work_end_to_end(tmp_path):
    """Run the actual patterns from `config/sync.example.yaml` against
    a fake source to make sure the documented syntax still does what
    the docs say."""
    source = _resolved(tmp_path / "src")
    vault = _resolved(tmp_path / "vault")
    config = tmp_path / "sync.yaml"

    _make_source_files(
        source,
        "README.md",                              # root .md
        "memory-solution/README.md",             # nested .md
        "memory-solution/docs/TODO.md",          # excluded (exact)
        "memory-solution/docs/notes.md",         # nested .md
        "proj-a/node_modules/dep/CHANGELOG.md",  # excluded (node_modules)
        "other/CHANGELOG.md",                     # excluded (**/CHANGELOG.md)
        "regular/file.md",                        # plain include
    )
    _write_config(
        config, vault, source, target="t",
        include=["**/*.md"],
        exclude=[
            "memory-solution/docs/TODO.md",
            "*/node_modules/**/*.md",
            "**/CHANGELOG.md",
        ],
    )

    result = run_sync(config, vault, "--apply")
    assert result.returncode == 0, result.stderr

    expected = [
        "t/README.md",
        "t/memory-solution/README.md",
        "t/memory-solution/docs/notes.md",
        "t/regular/file.md",
    ]
    unexpected = [
        "t/memory-solution/docs/TODO.md",
        "t/proj-a",            # node_modules subtree
        "t/other/CHANGELOG.md",
    ]
    for rel in expected:
        assert (vault / "00Raw" / rel).is_file(), f"missing {rel}"
    for rel in unexpected:
        assert not (vault / "00Raw" / rel).exists(), f"unexpectedly synced {rel}"


# ---------------------------------------------------------------------------
# Misc contract: missing config, missing source, etc.
# ---------------------------------------------------------------------------


def test_missing_config_dies_with_example_hint(tmp_path):
    """No config file → exit non-zero with a message pointing at the
    bundled example, matching the contract used by `init_vault.py`."""
    vault = _resolved(tmp_path / "vault")
    bogus = tmp_path / "no-such-sync.yaml"
    assert not bogus.exists()
    result = run_sync(bogus, vault)
    assert result.returncode != 0
    assert "no-such-sync.yaml" in result.stderr
    assert "sync.example.yaml" in result.stderr
