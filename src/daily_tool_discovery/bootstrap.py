from __future__ import annotations

import os
import shutil
from pathlib import Path


def default_data_root() -> Path:
    env = os.environ.get("DAILY_TOOL_DISCOVERY_HOME")
    return Path(env) if env else Path.home() / ".daily-tool-discovery"


def ensure_data_root(data_root: Path, bundle_dir: Path) -> None:
    (data_root / "config").mkdir(parents=True, exist_ok=True)
    (data_root / "seeds").mkdir(parents=True, exist_ok=True)
    prof = data_root / "config" / "profile.toml"
    example = bundle_dir / "config" / "profile.example.toml"
    if not prof.exists() and example.exists():
        shutil.copy(example, prof)
    seed = data_root / "seeds" / "manual.jsonl"
    seed_example = bundle_dir / "seeds" / "manual.example.jsonl"
    if not seed.exists() and seed_example.exists():
        shutil.copy(seed_example, seed)
