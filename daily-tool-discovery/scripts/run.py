#!/usr/bin/env python3
"""Entry point for the self-contained Daily Tool Discovery skill."""
import sys

sys.dont_write_bytecode = True  # keep the installed skill dir free of __pycache__

from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent        # .../daily-tool-discovery/scripts
SKILL_ROOT = SCRIPTS.parent                      # .../daily-tool-discovery
sys.path.insert(0, str(SCRIPTS))                 # so `import daily_tool_discovery` works

from daily_tool_discovery.bootstrap import default_data_root, ensure_data_root
from daily_tool_discovery.cli import main

_ROOTED = {"discover", "dry-run", "feedback", "save", "deny", "browse"}


def _run() -> int:
    argv = sys.argv[1:]
    data_root = default_data_root()
    ensure_data_root(data_root, SKILL_ROOT)      # examples live under SKILL_ROOT/templates
    if argv and argv[0] in _ROOTED and "--root" not in argv:
        argv = [argv[0], "--root", str(data_root), *argv[1:]]
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(_run())
