"""Component-aware glob matching for `sync_raw.py`.

`fnmatch.fnmatch` is the wrong tool for path globs: on macOS it treats `*`
as "any chars including `/`" (so `*.md` matches `a/b/c.md`), and on
Windows it ignores case. This module implements gitignore-style
semantics, which is what the sync config docs already promise:

  - `*`       matches exactly one path component (no `/`)
  - `**`      matches zero or more path components
  - `?`       matches a single character within a component
  - `[abc]`   matches a character in the class (also ranges: `[a-z]`)
  - `[!abc]`  negation (fnmatch-style)
  - All other characters match literally (including `.`)
  - Patterns are case-sensitive and anchored at both ends — the
    whole path must match the whole pattern.

The pattern syntax matches gitignore, bash `globstar`, and ripgrep
`--glob`. Use `glob_match()` for one pattern; `matches_any()` for the
"include if any pattern matches" idiom that `sync_raw.py` needs.
"""
from __future__ import annotations

import fnmatch
from functools import lru_cache
from typing import Iterable


def glob_match(path: str, pattern: str) -> bool:
    """Return True if `path` matches the glob `pattern`.

    `path` is a slash-separated relative path with no leading or
    trailing slash. `pattern` follows the syntax in the module
    docstring.
    """
    return _match_glob(
        tuple(path.split("/")),
        tuple(pattern.split("/")),
        0,
        0,
    )


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    """Return True if `path` matches any of the given patterns."""
    return any(glob_match(path, p) for p in patterns)


@lru_cache(maxsize=None)
def _match_glob(
    path: tuple[str, ...],
    pat: tuple[str, ...],
    pi: int,
    pj: int,
) -> bool:
    """Recursive component matcher.

    Splits both path and pattern on `/` and walks them in lockstep.
    `**` is the only multi-component wildcard; everything else is
    handled by `fnmatch.fnmatchcase` for within-component matching
    (which gives us `*`, `?`, `[...]` and case-sensitivity for free).
    """
    # Anchored end: pattern exhausted means path must be exhausted.
    if pj == len(pat):
        return pi == len(path)

    if pat[pj] == "**":
        # Zero-or-more components: try consuming 0, 1, 2, ... from the
        # path and recursing. The range upper bound is `len(path) + 1`
        # so the "consume zero" case (`k == pi`) is also tried.
        for k in range(pi, len(path) + 1):
            if _match_glob(path, pat, k, pj + 1):
                return True
        return False

    # Non-`**` components need a real path component to match against.
    if pi >= len(path):
        return False

    # Within-component match (handles `*`, `?`, `[abc]`, literals).
    if fnmatch.fnmatchcase(path[pi], pat[pj]):
        return _match_glob(path, pat, pi + 1, pj + 1)
    return False
