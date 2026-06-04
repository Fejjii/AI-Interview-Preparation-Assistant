#!/usr/bin/env python3
"""Run deterministic evaluation tests (no OpenAI API key required)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/evaluations",
        "-v",
        "--tb=short",
    ]
    print("Running:", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=root, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
