from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_run_dry_run_smoke(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    env = dict(os.environ)
    env["DAILY_TOOL_DISCOVERY_HOME"] = str(home)

    run_py = repo_root / "daily-tool-discovery" / "scripts" / "run.py"
    result = subprocess.run(
        [sys.executable, str(run_py), "dry-run"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (home / "briefings").is_dir()
