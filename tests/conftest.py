from __future__ import annotations

"""
Pytest configuration for this repository.

This project uses a `src/` layout but is not installed as a package when running tests.
We add `src/` to `sys.path` so `import interview_app...` works in all environments.
"""

import sys
from pathlib import Path


def pytest_configure() -> None:
    """
    Ensure `src/` is importable when running tests without installing the package.
    """

    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
