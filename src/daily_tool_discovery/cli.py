from __future__ import annotations

import argparse
import json
from datetime import date as date_type
from pathlib import Path
from typing import Any, Iterable

from daily_tool_discovery.briefing import render_briefing
from daily_tool_discovery.curated_sources import (
    discover_curated_candidates,
    discover_github_search_candidates,
    load_curated_sources,
    load_github_search_sources,
)
from daily_tool_discovery.feedback import FeedbackRecord, append_feedback
from daily_tool_discovery.models import Candidate
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


def run_discover(
    root: Path,
    date: str | None = None,
    sources_path: Path | None = None,
    limit: int = 80,
) -> None:
    current_date = _normalize_date(date)
    config_path = _resolve_sources_path(root, sources_path)

    taste_seeds = _load_optional_manual_seeds(root, current_date)
    github_searches = load_github_search_sources(config_path)
    github_quota = _github_search_quota(limit, has_github_searches=bool(github_searches))
    curated_quota = max(limit - github_quota, 0)

    candidates = discover_curated_candidates(
        load_curated_sources(config_path),
        discovered_at=current_date,
        limit=curated_quota,
    )
    candidates.extend(
        discover_github_search_candidates(
            github_searches,
            discovered_at=current_date,
            limit=github_quota,
        )
    )

    candidates = _apply_taste_profile(
        _exclude_manual_seed_urls(_dedupe_candidates(candidates), taste_seeds),
        taste_seeds,
    )
    candidate_path = root / "candidates" / f"{current_date}.jsonl"
    briefing_path = root / "briefings" / f"{current_date}.md"

    _write_jsonl(candidate_path, [candidate.to_dict() for candidate in candidates])
    selected = select_daily_candidates(candidates)

    briefing_path.parent.mkdir(parents=True, exist_ok=True)
    briefing_path.write_text(render_briefing(current_date, selected), encoding="utf-8")


def _load_optional_manual_seeds(root: Path, discovered_at: str) -> list[Candidate]:
    seed_path = root / "seeds" / "manual.jsonl"
    if not seed_path.exists():
        return []
    return load_manual_seeds(seed_path, discovered_at=discovered_at)


def _exclude_manual_seed_urls(
    candidates: list[Candidate], taste_seeds: list[Candidate]
) -> list[Candidate]:
    seed_urls = {_normalize_url(seed.url) for seed in taste_seeds}
    if not seed_urls:
        return candidates
    return [candidate for candidate in candidates if _normalize_url(candidate.url) not in seed_urls]


def _apply_taste_profile(
    candidates: list[Candidate], taste_seeds: list[Candidate]
) -> list[Candidate]:
    if not taste_seeds:
        return candidates

    taste_tags = {tag for seed in taste_seeds for tag in seed.tags}
    taste_kinds = {seed.kind for seed in taste_seeds}
    profiled: list[Candidate] = []
    for candidate in candidates:
        matching_tags = sorted(set(candidate.tags) & taste_tags)
        kind_match = candidate.kind in taste_kinds
        if not matching_tags:
            profiled.append(candidate)
            continue

        metadata = dict(candidate.metadata)
        metadata["taste_profile_match"] = True
        metadata["taste_profile_tags"] = matching_tags
        metadata["taste_profile_kind_match"] = kind_match
        profiled.append(
            Candidate(
                id=candidate.id,
                name=candidate.name,
                url=candidate.url,
                source=candidate.source,
                summary=candidate.summary,
                tags=candidate.tags,
                kind=candidate.kind,
                discovered_at=candidate.discovered_at,
                metadata=metadata,
            )
        )
    return profiled


def _github_search_quota(limit: int, has_github_searches: bool) -> int:
    if not has_github_searches or limit <= 0:
        return 0
    return min(20, max(10, (limit + 3) // 4), limit)


def _normalize_url(value: str) -> str:
    return value.removesuffix(".git").rstrip("/").lower()


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


def _resolve_sources_path(root: Path, sources_path: Path | None) -> Path:
    if sources_path is not None:
        return sources_path
    configured = root / "config" / "sources.toml"
    if configured.exists():
        return configured
    return root / "config" / "sources.example.toml"


def _dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    unique: dict[str, Candidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.id.lower(), candidate)
    return list(unique.values())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily-tool-discovery")
    subcommands = parser.add_subparsers(dest="command", required=True)

    dry_run = subcommands.add_parser(
        "dry-run", help="Run the local manual-seed briefing pipeline"
    )
    dry_run.add_argument("--root", type=Path, default=Path.cwd())
    dry_run.add_argument("--date", default=None)

    discover = subcommands.add_parser(
        "discover", help="Discover candidates from curated sources and GitHub search"
    )
    discover.add_argument("--root", type=Path, default=Path.cwd())
    discover.add_argument("--date", default=None)
    discover.add_argument("--sources", type=Path, default=None)
    discover.add_argument("--limit", type=int, default=80)

    feedback = subcommands.add_parser(
        "feedback", help="Append lightweight feedback for a candidate"
    )
    feedback.add_argument("--root", type=Path, default=Path.cwd())
    feedback.add_argument("--date", required=True)
    feedback.add_argument("--candidate-id", required=True)
    feedback.add_argument("--verdict", choices=["tried", "saved", "ignored"], required=True)
    feedback.add_argument("--value", required=True)
    feedback.add_argument("--note", default="")

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

    if args.command == "discover":
        try:
            run_discover(
                root=args.root,
                date=args.date,
                sources_path=args.sources,
                limit=args.limit,
            )
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        return 0

    if args.command == "feedback":
        try:
            feedback_date = _normalize_date(args.date)
            append_feedback(
                args.root / "feedback.jsonl",
                FeedbackRecord(
                    date=feedback_date,
                    candidate_id=args.candidate_id,
                    verdict=args.verdict,
                    value=args.value,
                    note=args.note,
                ),
            )
        except ValueError as exc:
            parser.error(str(exc))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
