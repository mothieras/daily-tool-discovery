from __future__ import annotations

from pathlib import Path

from daily_tool_discovery.jsonl_store import read_jsonl
from daily_tool_discovery.models import Candidate


def load_manual_seeds(path: Path, discovered_at: str) -> list[Candidate]:
    seeds: list[Candidate] = []
    for row in read_jsonl(path):
        url = str(row["url"])
        seeds.append(
            Candidate(
                id=f"manual:{url}",
                name=str(row["name"]),
                url=url,
                source="manual",
                summary=str(row.get("summary", "")),
                tags=[str(tag) for tag in row.get("tags", [])],
                kind=row.get("kind", "other"),
                discovered_at=discovered_at,
                metadata={"manual_seed": True},
            )
        )
    return seeds
