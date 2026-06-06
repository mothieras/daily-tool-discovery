from __future__ import annotations

import argparse
from datetime import date as date_type
from pathlib import Path

from daily_tool_discovery.briefing import render_briefing
from daily_tool_discovery.jsonl_store import append_jsonl
from daily_tool_discovery.ranking import select_daily_candidates
from daily_tool_discovery.seeds import load_manual_seeds


def run_dry_run(root: Path, date: str | None = None) -> None:
    current_date = date or date_type.today().isoformat()
    seed_path = root / "seeds" / "manual.jsonl"
    candidates = load_manual_seeds(seed_path, discovered_at=current_date)

    candidate_path = root / "candidates" / f"{current_date}.jsonl"
    briefing_path = root / "briefings" / f"{current_date}.md"

    append_jsonl(candidate_path, [candidate.to_dict() for candidate in candidates])
    selected = select_daily_candidates(candidates)

    briefing_path.parent.mkdir(parents=True, exist_ok=True)
    briefing_path.write_text(render_briefing(current_date, selected), encoding="utf-8")


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
        run_dry_run(root=args.root, date=args.date)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
