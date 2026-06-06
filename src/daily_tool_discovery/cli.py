from __future__ import annotations

import argparse
import json
from datetime import date as date_type
from pathlib import Path
from typing import Any, Iterable

from daily_tool_discovery.briefing import render_briefing
from daily_tool_discovery.ranking import select_daily_candidates
from daily_tool_discovery.seeds import load_manual_seeds


def run_dry_run(root: Path, date: str | None = None) -> None:
    current_date = _normalize_date(date)
    seed_path = root / "seeds" / "manual.jsonl"
    if not seed_path.exists():
        raise FileNotFoundError(f"manual seed file not found: {seed_path}")

    candidates = load_manual_seeds(seed_path, discovered_at=current_date)

    candidate_path = root / "candidates" / f"{current_date}.jsonl"
    briefing_path = root / "briefings" / f"{current_date}.md"

    _write_jsonl(candidate_path, [candidate.to_dict() for candidate in candidates])
    selected = select_daily_candidates(candidates)

    briefing_path.parent.mkdir(parents=True, exist_ok=True)
    briefing_path.write_text(render_briefing(current_date, selected), encoding="utf-8")


def _normalize_date(value: str | None) -> str:
    raw_date = value or date_type.today().isoformat()
    try:
        return date_type.fromisoformat(raw_date).isoformat()
    except ValueError as exc:
        raise ValueError(f"Invalid dry-run date: {raw_date!r}") from exc


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    temp_path.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily-tool-discovery")
    subcommands = parser.add_subparsers(dest="command", required=True)

    dry_run = subcommands.add_parser(
        "dry-run", help="Run the local manual-seed briefing pipeline"
    )
    dry_run.add_argument("--root", type=Path, default=Path.cwd())
    dry_run.add_argument("--date", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    if argv == []:
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "dry-run":
        try:
            run_dry_run(root=args.root, date=args.date)
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
