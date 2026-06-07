#!/usr/bin/env python3
"""Self-contained entry point: works from the repo (src/ layout) or a flattened skill bundle."""
import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent
for candidate in (BUNDLE / "src", BUNDLE):
    if (candidate / "daily_tool_discovery").is_dir():
        sys.path.insert(0, str(candidate))
        break

from daily_tool_discovery.bootstrap import default_data_root, ensure_data_root
from daily_tool_discovery.cli import main

_ROOTED = {"discover", "dry-run", "feedback", "save", "deny"}


def _run() -> int:
    argv = sys.argv[1:]
    data_root = default_data_root()
    ensure_data_root(data_root, BUNDLE)
    if argv and argv[0] in _ROOTED and "--root" not in argv:
        argv = [argv[0], "--root", str(data_root), *argv[1:]]
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(_run())
