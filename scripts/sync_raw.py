#!/usr/bin/env python3
"""Mirror files from project trees into 00Raw/.

Each `syncs` entry in the config declares a `source` directory and a
`target` path *relative* to `<vault>/00Raw/`. Files under `source` that
match the `include` patterns and don't match the `exclude` patterns are
copied to `<vault>/00Raw/<target>/<relative-to-source>`. For example,
with `source: ~/agent-workspaces` and `target: local/agent-workspaces`,
the file `~/agent-workspaces/memory-solution/README.md` lands at
`<vault>/00Raw/local/agent-workspaces/memory-solution/README.md`.

The actual copy is delegated to `rsync`, which gives us incremental
copies and directory handling for free. We compute the filter list in
Python so the config semantics stay simple (no rsync rule ordering
gotchas), then hand off to rsync with `--files-from=-`.

The script is a dry run by default — pass `--apply` to actually write.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts._lib.config import load_yaml
    from scripts._lib.glob import matches_any as _matches
    from scripts._lib.paths import (
        RAW,
        SKIP_NAMES,
        die,
        info,
        section,
        vault_root,
    )
else:
    from _lib.config import load_yaml
    from _lib.glob import matches_any as _matches
    from _lib.paths import (
        RAW,
        SKIP_NAMES,
        die,
        info,
        section,
        vault_root,
    )


DEFAULT_CONFIG = Path(__file__).resolve().parent / "config" / "sync.yaml"

# Always-excluded, regardless of config. These are tooling/build dirs that
# almost never contain useful memory material and would otherwise dominate
# the rsync traversal.
HARD_EXCLUDES = [
    ".obsidian",
    ".git",
    ".DS_Store",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "build",
    "dist",
    ".next",
    ".turbo",
]


def _validate_target(target: str) -> Path:
    """Parse and validate the `target` field. Returns the path *parts* as a tuple."""
    if not target:
        die("sync entry has empty `target`")
    if target.startswith("/"):
        die(f"sync `target` must be relative, got {target!r}")
    parts = Path(target).parts
    if any(p in ("..", "") for p in parts):
        die(f"sync `target` contains '..' or empty segment: {target!r}")
    return Path(target)


def _list_files(
    source: Path,
    include: list[str] | None,
    exclude: list[str] | None,
) -> list[Path]:
    """Return the files (relative to `source`) that pass the filter rules.

    `include=None` means "every file under `source`" (any extension).
    Use `include` to limit by extension, name, or path pattern — e.g.
    `["**/*.md"]` for markdown-only or `["**/*.md", "**/*.png"]` for
    markdown plus images. Hard excludes are always applied in addition
    to user `exclude` patterns.

    Pattern matching is delegated to `_lib/glob.py`, which implements
    gitignore-style component-aware semantics (`*` does not cross `/`,
    `**` matches zero or more components). See that module's docstring.
    """
    out: list[Path] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        rel_str = str(rel)
        # Hard exclude on any path segment.
        if any(part in SKIP_NAMES or part in HARD_EXCLUDES for part in rel.parts):
            continue
        if include is not None and not _matches(rel_str, include):
            continue
        if exclude is not None and _matches(rel_str, exclude):
            continue
        out.append(rel)
    return out


def _dest_root(vault_root_path: Path, target: str) -> Path:
    return vault_root_path / RAW / target


def _prune(
    dest_root: Path,
    expected_rels: set[Path],
    apply: bool,
) -> list[Path]:
    """Delete files in dest_root that aren't in expected_rels.

    Returns the list (in either form: removed or plan-removed). Only
    touches files; never removes empty directories. Walks every file
    type so that non-markdown files (when synced) are also pruned on
    a `--delete` run.
    """
    if not dest_root.exists():
        return []
    removed: list[Path] = []
    for path in sorted(dest_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dest_root)
        if rel not in expected_rels:
            removed.append(path)
            if apply:
                path.unlink()
    return removed


def _run_rsync(
    source: Path,
    dest_root: Path,
    rels: list[Path],
    apply: bool,
    delete: bool,
) -> subprocess.CompletedProcess:
    """Invoke rsync with a stdin file list of relative paths."""
    args = [
        "rsync",
        "-a",  # archive: recursive, preserve perms/mtimes, etc.
        "-i",  # itemize: emit a per-file status line. Cheap; lets us count.
        "--files-from=-",  # read list of relative paths from stdin
    ]
    if not apply:
        args.append("--dry-run")
    if delete:
        args.append("--delete")
    # We use a trailing slash on source so rsync treats it as a directory
    # to read from (not a directory to copy). Trailing slash on dest
    # matters less since we're listing files explicitly.
    args.append(str(source) + "/")
    args.append(str(dest_root) + "/")

    # rsync reads the file list as newline-separated by default. Each
    # entry is a path relative to the source root.
    payload = "\n".join(str(r) for r in rels) + "\n"
    return subprocess.run(
        args,
        input=payload.encode(),
        check=False,
        capture_output=True,
    )


def sync_one(
    entry: dict,
    apply: bool,
    vault_root_path: Path,
) -> tuple[int, int, int]:
    """Sync one entry. Returns (copied_or_planned, removed, unchanged)."""
    source_raw = entry.get("source")
    target_raw = entry.get("target")
    if not source_raw:
        die(f"sync entry missing `source`: {entry}")
    if not target_raw:
        die(f"sync entry missing `target`: {entry}")

    source = Path(str(source_raw)).expanduser().resolve()
    if not source.exists():
        die(f"sync source does not exist: {source}")
    if not source.is_dir():
        die(f"sync source is not a directory: {source}")

    target = _validate_target(str(target_raw))
    dest_root = _dest_root(vault_root_path, str(target))
    include = entry.get("include")
    exclude = entry.get("exclude")
    delete = bool(entry.get("delete", False))

    rels = _list_files(source, include, exclude)
    expected_rels = set(rels)
    info(f"[{target}] {len(rels)} files match")

    # Initialise the counts up-front so the empty-rels branch below
    # doesn't trip an UnboundLocalError on return. (rsync's per-file
    # log loop, when entered, may increment these.)
    transferred = 0
    no_op = 0

    if rels:
        # Make sure the dest dir exists so rsync can write into it on
        # the first run. Idempotent and cheap; needed because the
        # `--files-from` mode doesn't auto-create parents.
        dest_root.mkdir(parents=True, exist_ok=True)

        result = _run_rsync(source, dest_root, rels, apply, delete)
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            die(f"rsync failed for {target}:\n{stderr}")
        # In itemize mode, rsync prints lines like
        #   `>f++++++ README.md`        (file would be / is being sent)
        #   `.f........ README.md`      (no change — canonical rsync only)
        #   `*deleting   extra.md`     (with --delete)
        #   `cd+++++++ sub/`            (intermediate dir)
        # The itemize code is action + type + attribute flags. The
        # exact width depends on the rsync implementation (openrsync
        # on macOS uses 9 chars; canonical samba rsync uses 11), so
        # we split on the first space rather than slicing. Also,
        # openrsync is silent on identical files (no `.f` line at
        # all), so we derive the no-op count as `total - transferred`
        # for an implementation-independent answer.
        verb = "would create" if not apply else "creating"
        for line in result.stdout.decode(errors="replace").splitlines():
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            code, src_rel_str = parts[0], parts[1]
            if code.startswith("*deleting"):
                continue
            if len(code) < 2:
                continue
            if code[0] == ">" and code[1] == "f":
                transferred += 1
                if not src_rel_str:
                    continue
                dest_path = dest_root / src_rel_str
                try:
                    dest_rel = dest_path.relative_to(vault_root_path)
                except ValueError:
                    # Defensive: dest_root is built from vault_root_path,
                    # so this shouldn't happen, but if it ever does we
                    # fall back to the dest_root-relative path.
                    dest_rel = dest_path.relative_to(dest_root)
                info(f"[{target}] {verb}: {dest_rel}")
        no_op = len(rels) - transferred
        info(
            f"[{target}] "
            f"{'planned transfers' if not apply else 'transfers'}: {transferred}, "
            f"no-op entries: {no_op}"
        )
    else:
        info(f"[{target}] nothing to transfer")

    removed_count = 0
    if delete:
        removed = _prune(dest_root, expected_rels, apply)
        removed_count = len(removed)
        for r in removed:
            info(f"[{target}] {'removed' if apply else 'plan-remove'} {r.relative_to(dest_root)}")
    return (transferred, removed_count, no_op)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"YAML config file (default: {DEFAULT_CONFIG}).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write files. Without this flag the script is a dry run.",
    )
    parser.add_argument(
        "--vault-root",
        type=Path,
        default=vault_root(),
        help="Override the vault root (default: ~/Documents/agentstuffs).",
    )
    args = parser.parse_args()

    if not args.config.exists():
        die(
            f"config file not found: {args.config}\n"
            f"Copy scripts/config/sync.example.yaml to {args.config} and edit it."
        )

    cfg = load_yaml(args.config)
    if not isinstance(cfg, dict):
        die(f"config root must be a mapping, got {type(cfg).__name__}")
    syncs = cfg.get("syncs")
    if not isinstance(syncs, list) or not syncs:
        die("config has no `syncs` list")

    section(f"Vault: {args.vault_root}")
    section("Mode: " + ("APPLY" if args.apply else "DRY-RUN (use --apply to write)"))
    section("Syncs:")

    totals = [0, 0, 0]  # transferred, removed, unchanged
    for entry in syncs:
        if not isinstance(entry, dict):
            die(f"sync entry must be a mapping, got {type(entry).__name__}: {entry}")
        # Tolerate a missing example source in the example config: warn
        # and skip rather than aborting the whole run.
        source_raw = entry.get("source")
        if source_raw:
            sp = Path(str(source_raw)).expanduser().resolve()
            if not sp.exists():
                print(f"warning: skipping sync (source missing): {sp}", file=sys.stderr)
                continue
        t, r, n = sync_one(entry, args.apply, args.vault_root)
        totals[0] += t
        totals[1] += r
        totals[2] += n

    section("Summary")
    print(f"  transferred/planned: {totals[0]}")
    print(f"  removed/plan-remove: {totals[1]}")
    print(f"  unchanged:           {totals[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
