from __future__ import annotations

from pathlib import Path
from typing import Any

from daily_tool_discovery.jsonl_store import read_jsonl_rows
from daily_tool_discovery.models import Candidate


def load_manual_seeds(path: Path, discovered_at: str) -> list[Candidate]:
    seeds: list[Candidate] = []
    for line_number, row in read_jsonl_rows(path):
        url = str(_required_field(row, path, line_number, "url"))
        tags = row.get("tags", [])
        if not isinstance(tags, list):
            raise ValueError(
                f"Invalid manual seed at {path}:{line_number}: tags must be a list"
            )
        try:
            seed = Candidate(
                id=f"manual:{url}",
                name=str(_required_field(row, path, line_number, "name")),
                url=url,
                source="manual",
                summary=str(row.get("summary", "")),
                tags=[str(tag) for tag in tags],
                kind=row.get("kind", "other"),
                discovered_at=discovered_at,
                metadata={"manual_seed": True},
            )
        except ValueError as exc:
            raise ValueError(
                f"Invalid manual seed at {path}:{line_number}: {exc}"
            ) from exc
        seeds.append(seed)
    return seeds


def _required_field(
    row: dict[str, Any], path: Path, line_number: int, field_name: str
) -> Any:
    try:
        return row[field_name]
    except KeyError as exc:
        raise ValueError(
            f"Invalid manual seed at {path}:{line_number}: missing required field "
            f"{field_name!r}"
        ) from exc
