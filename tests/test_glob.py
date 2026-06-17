"""Tests for `scripts/_lib/glob.py` — component-aware pattern matching.

These cover the gitignore-style semantics that `sync_raw.py` relies on.
Cases are grouped by feature; every entry has at least one positive
("matches") and one negative ("doesn't match") example to lock in
both directions of the boundary.
"""
from __future__ import annotations

import pytest

from scripts._lib.glob import glob_match, matches_any


# ---------------------------------------------------------------------------
# `*` — single component, no slash-crossing
# ---------------------------------------------------------------------------


class TestSingleStar:
    def test_matches_at_root(self):
        assert glob_match("README.md", "*.md")
        assert glob_match("foo.md", "*.md")

    def test_does_not_cross_slash(self):
        # The original `fnmatch.fnmatch` bug: `*` matched across `/`.
        # A `*` in a pattern segment must consume only that segment.
        assert not glob_match("a/b/c.md", "*.md")
        assert not glob_match("a/b/c.md", "*/*.md")
        # Sanity: a 3-component pattern *does* match a 3-component path
        # (this is the corollary — the bug was about crossing /, not
        # about the number of components).
        assert glob_match("a/b/c.md", "*/*/*.md")

    def test_mid_component_glob(self):
        assert glob_match("prefix-foo.md", "prefix-*.md")
        assert glob_match("foo-suffix.md", "*-suffix.md")
        assert glob_match("pre-x-suf.md", "pre-*-suf.md")

    def test_empty_path_component_matches_star(self):
        # fnmatch (and therefore us) treats `*` as "zero or more chars"
        # within a component, so an empty component matches `*`. We
        # don't try to reject this — real file paths from
        # `Path.relative_to` are never empty in practice, and being
        # fnmatch-compatible is the documented contract for `*`.
        assert glob_match("", "*")

    def test_literal_dot_is_literal(self):
        # fnmatch treats `.` as literal too; sanity check.
        assert glob_match("foo.md", "*.md")
        assert not glob_match("fooxmd", "*.md")


# ---------------------------------------------------------------------------
# `**` — zero or more components
# ---------------------------------------------------------------------------


class TestDoubleStar:
    def test_alone_matches_anything(self):
        assert glob_match("a", "**")
        assert glob_match("a/b/c.md", "**")
        assert glob_match("README.md", "**")

    def test_matches_at_root(self):
        # The classic `**/*.md` must also catch the root-level README.
        assert glob_match("README.md", "**/*.md")
        assert glob_match("CHANGELOG.md", "**/CHANGELOG.md")

    def test_matches_at_depth(self):
        assert glob_match("a/README.md", "**/*.md")
        assert glob_match("a/b/c/README.md", "**/*.md")
        assert glob_match("a/CHANGELOG.md", "**/CHANGELOG.md")

    def test_leading_literal_is_anchored(self):
        # `a/**/b` requires the path to start with `a`.
        assert not glob_match("x/a/b.md", "a/**/b.md")
        assert not glob_match("b.md", "a/**/b.md")

    def test_middle_double_star_zero_or_more(self):
        assert glob_match("a/b", "a/**/b")
        assert glob_match("a/x/b", "a/**/b")
        assert glob_match("a/x/y/b", "a/**/b")
        assert not glob_match("a/x/y/c", "a/**/b")

    def test_trailing_double_star(self):
        assert glob_match("docs/a.md", "docs/**")
        assert glob_match("docs/sub/b.md", "docs/**")
        # Trailing `**` requires the path to start with `docs/`.
        assert not glob_match("a/docs/x.md", "docs/**")

    def test_multiple_double_stars(self):
        assert glob_match("a/b/c", "a/**/b/**/c")
        assert glob_match("a/x/b/y/c", "a/**/b/**/c")
        assert glob_match("a/b/y/c", "a/**/b/**/c")
        # No `b` in path → can't match.
        assert not glob_match("a/x/y/z", "a/**/b/**/c")
        # Leading literal anchor isn't satisfied.
        assert not glob_match("x/a/b/c", "a/**/b/**/c")

    def test_does_not_match_when_intermediate_component_required(self):
        # `**/node_modules/**` requires the dir named node_modules.
        assert not glob_match("a/b.md", "**/node_modules/**")
        assert glob_match("a/node_modules/b.md", "**/node_modules/**")
        assert glob_match("a/node_modules/sub/b.md", "**/node_modules/**")


# ---------------------------------------------------------------------------
# `?` — exactly one character in a component
# ---------------------------------------------------------------------------


class TestQuestionMark:
    def test_matches_one_char(self):
        assert glob_match("a.md", "?.md")
        assert glob_match("abc", "a?c")

    def test_does_not_match_zero_chars(self):
        assert not glob_match("ac", "a?c")

    def test_does_not_match_two_chars(self):
        assert not glob_match("abbc", "a?c")
        assert not glob_match("ab.md", "?.md")

    def test_does_not_cross_slash(self):
        # `?` is single-component, like `*`.
        assert not glob_match("a/b.md", "?.md")


# ---------------------------------------------------------------------------
# `[...]` — character classes
# ---------------------------------------------------------------------------


class TestCharClass:
    def test_basic_class(self):
        assert glob_match("a.md", "[abc].md")
        assert glob_match("b.md", "[abc].md")
        assert not glob_match("d.md", "[abc].md")

    def test_range(self):
        assert glob_match("m.md", "[a-z].md")
        assert not glob_match("M.md", "[a-z].md")  # case-sensitive
        assert not glob_match("1.md", "[a-z].md")

    def test_fnmatch_negation_with_bang(self):
        # fnmatch uses `!` for negation; `^` is *not* a negation marker
        # in fnmatch (it's literal), so we don't accept it either.
        assert glob_match("d.md", "[!abc].md")
        assert not glob_match("a.md", "[!abc].md")
        # `^` is a literal char inside a class for fnmatch:
        assert not glob_match("d.md", "[^abc].md")
        assert glob_match("^.md", "[^abc].md")  # `^` itself matches


# ---------------------------------------------------------------------------
# Anchoring: whole path matches whole pattern
# ---------------------------------------------------------------------------


class TestAnchoring:
    def test_exact_path(self):
        assert glob_match("a/b.md", "a/b.md")

    def test_no_extra_components_at_end(self):
        assert not glob_match("a/b/c.md", "a/b.md")

    def test_no_extra_components_at_start(self):
        assert not glob_match("x/a/b.md", "a/b.md")

    def test_partial_match_is_not_a_match(self):
        # `a/b` doesn't appear as a substring match — the whole path
        # must match the whole pattern.
        assert not glob_match("a/b/c/d", "a/b")


# ---------------------------------------------------------------------------
# Case sensitivity
# ---------------------------------------------------------------------------


class TestCaseSensitivity:
    def test_extension_is_case_sensitive(self):
        assert not glob_match("README.md", "*.MD")
        assert not glob_match("README.MD", "*.md")

    def test_filename_is_case_sensitive(self):
        assert not glob_match("FOO.md", "foo.md")
        assert not glob_match("foo.md", "FOO.md")


# ---------------------------------------------------------------------------
# `matches_any` — convenience wrapper
# ---------------------------------------------------------------------------


class TestMatchesAny:
    def test_empty_patterns_is_false(self):
        # Convention: an empty list means "no patterns match".
        assert not matches_any("README.md", [])
        assert not matches_any("a/b.md", [])

    def test_single_matching_pattern(self):
        assert matches_any("README.md", ["**/*.md"])

    def test_first_pattern_matches(self):
        assert matches_any("a/b/c.md", ["*.md", "**/*.md"])

    def test_middle_pattern_matches(self):
        assert matches_any("a/b/c.md", ["foo", "**/*.md", "bar"])

    def test_last_pattern_matches(self):
        assert matches_any("a/b/c.md", ["foo", "bar", "**/*.md"])

    def test_no_pattern_matches(self):
        assert not matches_any("a/b/c.md", ["*.txt", "x/*.md", "nomatch"])

    def test_used_for_exclude_check(self):
        # The exclude idiom: any of the patterns excludes the file.
        exclude = ["**/TODO.md", "**/CHANGELOG.md"]
        assert matches_any("a/b/TODO.md", exclude)
        assert matches_any("CHANGELOG.md", exclude)
        assert not matches_any("a/b/notes.md", exclude)


# ---------------------------------------------------------------------------
# Real patterns from `config/sync.example.yaml`
# ---------------------------------------------------------------------------


EXAMPLE_INCLUDE = ["**/*.md"]
EXAMPLE_EXCLUDE = [
    "memory-solution/docs/TODO.md",
    "*/node_modules/**/*.md",
]
EXAMPLE_EXCLUDE_2 = ["**/CHANGELOG.md"]


class TestExampleConfigPatterns:
    """Lock in the patterns the bundled example config actually uses."""

    def test_include_catches_root(self):
        assert matches_any("README.md", EXAMPLE_INCLUDE)

    def test_include_catches_nested(self):
        assert matches_any("a/b/c.md", EXAMPLE_INCLUDE)
        assert matches_any("proj/sub/file.md", EXAMPLE_INCLUDE)

    def test_exclude_exact_path(self):
        assert matches_any("memory-solution/docs/TODO.md", EXAMPLE_EXCLUDE)

    def test_exclude_does_not_match_unrelated(self):
        assert not matches_any("memory-solution/docs/notes.md", EXAMPLE_EXCLUDE)
        assert not matches_any("other-project/docs/TODO.md", EXAMPLE_EXCLUDE)

    def test_exclude_node_modules_one_level_deep(self):
        # `*/node_modules/**/*.md` requires node_modules to be one
        # directory below the source root.
        assert matches_any("proj-a/node_modules/x/y.md", EXAMPLE_EXCLUDE)

    def test_exclude_node_modules_nested(self):
        assert matches_any("proj/node_modules/sub/deep/note.md", EXAMPLE_EXCLUDE)

    def test_exclude_node_modules_at_root_does_not_match(self):
        # Root-level node_modules isn't covered by `*/node_modules/**`
        # (would need `**/node_modules/**`).
        assert not matches_any("node_modules/x.md", EXAMPLE_EXCLUDE)

    def test_exclude_changelog_anywhere(self):
        assert matches_any("CHANGELOG.md", EXAMPLE_EXCLUDE_2)
        assert matches_any("a/CHANGELOG.md", EXAMPLE_EXCLUDE_2)
        assert matches_any("a/b/c/CHANGELOG.md", EXAMPLE_EXCLUDE_2)
        assert not matches_any("a/CHANGELOG.txt", EXAMPLE_EXCLUDE_2)


# ---------------------------------------------------------------------------
# Pathological patterns (graceful handling, not crashy)
# ---------------------------------------------------------------------------


class TestPathologicalPatterns:
    def test_trailing_slash_matches_nothing(self):
        # A trailing `/` produces an empty trailing component, which
        # can never match a real (non-empty) path component.
        assert not glob_match("a/b.md", "a/b/")

    def test_only_double_star_matches_anything(self):
        assert glob_match("a/b/c/d/e/f.md", "**")

    def test_pattern_with_only_stars(self):
        # `*/**` = one component, then zero or more. So `a` is fine
        # (one component for `*`, zero for `**`), and longer paths too.
        assert glob_match("a", "*/**")
        assert glob_match("a/b", "*/**")
        assert glob_match("a/b/c", "*/**")
