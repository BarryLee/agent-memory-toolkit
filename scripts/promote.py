#!/usr/bin/env python3
"""
Promote a note from 10Staging/ to 20Curated/.

Usage:
    promote.py <staging_path>
    
Example:
    promote.py ~/Documents/agentstuffs/10Staging/Projects/my-note.md

Behavior:
    - Copies the file to the matching path under 20Curated/
    - Preserves the relative category structure
    - Refuses to overwrite an existing curated file (use --force)
    - Optionally deletes the staging copy (--delete, off by default)
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

VAULT_ROOT = Path.home() / "Documents" / "agentstuffs"
STAGING_PREFIX = "10Staging"
CURATED_PREFIX = "20Curated"


def get_dest_path(staging_path: Path) -> Path:
    """Transform a staging path to its curated equivalent."""
    staging_str = str(staging_path)
    if STAGING_PREFIX not in staging_str:
        raise ValueError(f"File is not in {STAGING_PREFIX}/: {staging_path}")
    
    # Replace 10Staging with 20Curated in the path
    dest_str = staging_str.replace(STAGING_PREFIX, CURATED_PREFIX, 1)
    return Path(dest_str)


def promote(staging_path: Path, force: bool = False, delete: bool = False) -> bool:
    """Promote a staging note to curated."""
    staging_path = staging_path.resolve()
    
    # Validate staging path
    if not staging_path.exists():
        print(f"Error: File does not exist: {staging_path}", file=sys.stderr)
        return False
    
    if STAGING_PREFIX not in str(staging_path):
        print(f"Error: File is not in {STAGING_PREFIX}/", file=sys.stderr)
        return False
    
    dest_path = get_dest_path(staging_path)
    
    # Check for overwrite
    if dest_path.exists() and not force:
        print(f"Error: Destination already exists: {dest_path}", file=sys.stderr)
        print("Use --force to overwrite.", file=sys.stderr)
        return False
    
    # Ensure destination directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Copy (or move) the file
    if delete:
        shutil.move(str(staging_path), str(dest_path))
        print(f"Moved: {staging_path}")
    else:
        shutil.copy2(str(staging_path), str(dest_path))
        print(f"Copied: {staging_path}")
    
    print(f"  → {dest_path}")
    return True


def open_in_obsidian(file_path: Path) -> None:
    """Open the file in Obsidian via URI."""
    file_uri = file_path.as_uri()
    # obsidian://open?path=<encoded_path>
    obsidian_uri = f"obsidian://open?path={file_path}"
    os.system(f'open "{obsidian_uri}"')


def main():
    parser = argparse.ArgumentParser(description="Promote a note from 10Staging/ to 20Curated/")
    parser.add_argument("file", help="Path to the staging file")
    parser.add_argument("--force", action="store_true", help="Overwrite existing curated file")
    parser.add_argument("--delete", action="store_true", help="Delete staging file after promoting (default: keep it)")
    parser.add_argument("--no-open", action="store_true", help="Don't open the file in Obsidian after promoting")
    
    args = parser.parse_args()
    
    staging_path = Path(args.file).expanduser()
    success = promote(staging_path, force=args.force, delete=args.delete)
    
    if success and not args.no_open:
        dest_path = get_dest_path(staging_path)
        open_in_obsidian(dest_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
