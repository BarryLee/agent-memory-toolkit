"""YAML config loader. Requires PyYAML.

Install with: `pip3 install --user pyyaml` (or `brew install pyyaml` /
`uv pip install --system pyyaml`). We fail fast with a clear message if it
isn't present, rather than silently misparsing the config.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required for the memory-solution scripts.\n"
        "Install it with one of:\n"
        "  pip3 install --user pyyaml\n"
        "  uv pip install --system pyyaml\n"
        "  python3 -m pip install --user pyyaml\n"
        f"Original error: {e}"
    )


def load_yaml(path: Path) -> Any:
    """Load a YAML file. Returns whatever the root is (usually a dict)."""
    return yaml.safe_load(Path(path).read_text())
