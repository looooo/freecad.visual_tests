#!/usr/bin/env python3
"""
Run pytest under xvfb and exit with the real test result.
If the process crashes during shutdown (e.g. FreeCAD), use the exit status
saved by pytest_sessionfinish so that exit code 0 = all passed, 1 = some failed.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = PROJECT_ROOT / ".pytest_exitstatus"


def main() -> int:
    if STATUS_FILE.exists():
        try:
            STATUS_FILE.unlink()
        except OSError:
            pass

    result = subprocess.run(
        ["xvfb-run", "-s", "-screen 0 1920x1080x24", "pytest", "-s"],
        cwd=PROJECT_ROOT,
        env=os.environ,
    )

    # Prefer saved status when subprocess did not exit cleanly with 0
    saved = None
    if STATUS_FILE.exists():
        try:
            saved = int(STATUS_FILE.read_text().strip())
        except (ValueError, OSError):
            pass

    if result.returncode == 0:
        return 0
    # Subprocess returned 1 or crashed (139/-11 etc.): use saved status if available
    if saved is not None:
        return 0 if saved == 0 else 1
    if result.returncode == 1:
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
