"""Unit tests for `scripts._lib.templates` (load + render)."""
from __future__ import annotations

import pytest

from scripts._lib import templates


# --- render(): basic substitution -------------------------------------------


def test_basic_substitution():
    assert templates.render("Hello {{name}}!", {"name": "world"}) == "Hello world!"


def test_multiple_vars():
    assert templates.render("{{a}}/{{b}}", {"a": "foo", "b": "bar"}) == "foo/bar"


def test_same_var_used_twice():
    assert templates.render("{{x}} and {{x}}", {"x": "Z"}) == "Z and Z"


def test_substitution_with_adjacent_text():
    """A placeholder right next to other text should still be matched."""
    assert templates.render("a{{x}}b", {"x": "Y"}) == "aYb"


# --- render(): literal characters that look like placeholders ---------------


def test_no_placeholders_returns_unchanged():
    assert templates.render("plain text", {}) == "plain text"


def test_literal_single_braces_untouched():
    """Single `{` and `}` (not doubled) are always literal."""
    assert templates.render("plain {single} braces", {}) == "plain {single} braces"


def test_unmatched_opening_double_brace_stays():
    assert templates.render("a {{broken string", {"x": "y"}) == "a {{broken string"


def test_unmatched_closing_double_brace_stays():
    assert templates.render("a broken}} string", {}) == "a broken}} string"


def test_empty_placeholder_stays_literal():
    """`{{}}` is not a valid identifier-bearing placeholder."""
    assert templates.render("a {{}} b", {}) == "a {{}} b"


def test_dot_in_name_does_not_match():
    """`{{foo.bar}}` is not a valid identifier (dots disallowed), so stays literal."""
    out = templates.render("a {{foo.bar}} b {{foo}} c", {"foo": "X"})
    assert out == "a {{foo.bar}} b X c"


def test_whitespace_inside_placeholder_stays_literal():
    """`{{ name }}` (with spaces) is not matched — only `{{name}}` is."""
    out = templates.render("{{ name }} and {{name}}", {"name": "X"})
    assert out == "{{ name }} and X"


def test_digit_leading_name_stays_literal():
    """`{{1foo}}` is not a valid identifier (must start with letter/_)."""
    out = templates.render("{{1foo}} and {{foo1}}", {"foo1": "X"})
    assert out == "{{1foo}} and X"


def test_code_blocks_with_braces_untouched():
    """Markdown code blocks commonly contain `{` / `}` — must pass through."""
    code = "```\nif (x) { y(); }\n```"
    assert templates.render(code, {}) == code


def test_markdown_link_with_braces_untouched():
    """`{...}` inside a markdown link target should not be misinterpreted."""
    md = "[link](https://example.com/foo{bar})"
    assert templates.render(md, {}) == md


# --- render(): error handling ------------------------------------------------


def test_unknown_var_raises_keyerror():
    with pytest.raises(KeyError, match="missing"):
        templates.render("{{missing}}", {})


def test_partially_known_vars_still_raise():
    """If any placeholder is unknown, fail loudly — don't silently drop it."""
    with pytest.raises(KeyError):
        templates.render("{{known}} and {{unknown}}", {"known": "K"})


# --- load(): file reading ----------------------------------------------------


def test_load_reads_file(tmp_path):
    p = tmp_path / "t.tmpl"
    p.write_text("hello {{name}}")
    assert templates.load(p) == "hello {{name}}"


def test_load_returns_raw_text_no_rendering(tmp_path):
    """`load` is a pure file read — it does NOT render placeholders."""
    p = tmp_path / "t.tmpl"
    p.write_text("{{still_literal}}")
    assert templates.load(p) == "{{still_literal}}"
