"""Pytest configuration: make the `scripts` package importable.

When pytest discovers tests under `tests/`, the project root needs to
be on `sys.path` so the test files can `from scripts._lib import …`.
Adding the root here (rather than in each test file) keeps the
imports in the test files clean.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
