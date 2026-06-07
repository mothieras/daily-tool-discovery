from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from daily_tool_discovery.jsonl_store import read_jsonl
from daily_tool_discovery.models import Candidate, CandidateDecision


def record_surfaced(
    path: Path,
    surfaced_date: str,
    selected: list[tuple[Candidate, CandidateDecision]],
) -> None:
    existing = [row for row in read_jsonl(path) if row.get("date") != surfaced_date]
    new_rows = [
        {"date": surfaced_date, "candidate_id": candidate.id, "action": decision.action}
        for candidate, decision in selected
    ]
    _write_all(path, existing + new_rows)


def load_recent_surfaced_ids(path: Path, today: date, days: int) -> set[str]:
    ids: set[str] = set()
    for row in read_jsonl(path):
        raw_date = row.get("date")
        candidate_id = row.get("candidate_id")
        if not raw_date or not candidate_id:
            continue
        try:
            row_date = date.fromisoformat(str(raw_date)[:10])
        except ValueError:
            continue
        if (today - row_date).days < days:
            ids.add(str(candidate_id))
    return ids


def _write_all(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    temp_path.replace(path)
