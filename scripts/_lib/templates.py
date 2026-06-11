"""Markdown template loading and rendering.

Templates live as plain `.md.tmpl` files in
`scripts/config/templates/<scope>/` (e.g. `vault/`, `bank/`). They
are regular markdown with `{{name}}` placeholders that the caller
fills in at render time.

Placeholder syntax:
  - `{{name}}` — substituted with the value of `name` from the
    `vars` dict. `name` must be a Python identifier
    (letters/digits/underscore, starting with a letter or underscore).
  - Anything that does not match the placeholder regex is left
    untouched, so literal `{` / `}` braces in markdown are safe.
  - Unknown placeholders raise `KeyError` so a typo in either the
    template or the caller fails loudly rather than silently
    dropping content.

The `{{...}}` syntax is intentionally non-YAML, non-Markdown, and
non-`string.Template`-style, so a template file is just a markdown
file that an editor (and Obsidian) can preview as-is.
"""
from __future__ import annotations

import re
from pathlib import Path

# Strict identifier match: a-z, A-Z, 0-9, underscore, must not start
# with a digit. Anything else (including spaces, dots, hyphens) means
# the `{{...}}` is literal text and is left alone by `re.sub`.
_PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")


def load(path: Path) -> str:
    """Read a template file. Returns the raw text (no rendering)."""
    return Path(path).read_text()


def render(text: str, vars: dict[str, str]) -> str:
    """Substitute `{{name}}` placeholders in `text` with `vars[name]`.

    Unknown placeholders raise `KeyError`. Unmatched `{{` / `}}` are
    left as-is (they will not be matched by the regex).
    """
    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name not in vars:
            raise KeyError(f"unknown template variable: {name!r}")
        return str(vars[name])

    return _PLACEHOLDER_RE.sub(repl, text)
