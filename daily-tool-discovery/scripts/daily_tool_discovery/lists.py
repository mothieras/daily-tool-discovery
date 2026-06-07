from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path


def _repo_slug(candidate_id: str) -> str:
    return candidate_id.split(":", 1)[-1] if ":" in candidate_id else candidate_id


def is_denied(candidate_id: str, patterns) -> bool:
    slug = _repo_slug(candidate_id)
    return any(fnmatch(slug, p) for p in patterns)


def load_denylist(path: Path, static_patterns=()) -> tuple[str, ...]:
    patterns = list(static_patterns)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    seen: list[str] = []
    for p in patterns:
        if p not in seen:
            seen.append(p)
    return tuple(seen)


def append_denylist(path: Path, pattern: str) -> None:
    existing = load_denylist(path)
    if pattern in existing:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(pattern + "\n")
