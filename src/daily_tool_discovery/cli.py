from __future__ import annotations

import argparse
import json
import os
from datetime import date as date_type
from pathlib import Path
from typing import Any, Iterable

from daily_tool_discovery.briefing import render_briefing
from daily_tool_discovery.config import load_config
from daily_tool_discovery.curated_sources import (
    discover_curated_candidates,
    discover_github_search_candidates,
    load_curated_sources,
    load_github_search_sources,
)
from daily_tool_discovery.feedback import (
    FeedbackRecord,
    append_feedback,
    load_feedback_signals,
)
from daily_tool_discovery.github_client import GitHubClient
from daily_tool_discovery.history import load_recent_surfaced_ids, record_surfaced
from daily_tool_discovery.jsonl_store import read_jsonl
from daily_tool_discovery.models import Candidate
from daily_tool_discovery.ranking import select_daily_candidates, select_from_pool
from daily_tool_discovery.seeds import load_manual_seeds
from daily_tool_discovery.trust import annotate_trust, assess_trust, publisher_is_suspicious


def _make_github_client() -> GitHubClient:
    return GitHubClient(token=os.environ.get("GITHUB_TOKEN"))


def run_dry_run(root: Path, date: str | None = None) -> None:
    current_date = _normalize_date(date)
    today = date_type.fromisoformat(current_date)
    seed_path = root / "seeds" / "manual.jsonl"
    if not seed_path.exists():
        raise FileNotFoundError(f"manual seed file not found: {seed_path}")

    candidates = load_manual_seeds(seed_path, discovered_at=current_date)
    _write_jsonl(root / "candidates" / f"{current_date}.jsonl", [c.to_dict() for c in candidates])
    selected = select_from_pool(candidates, today=today)
    _write_briefing(root, current_date, selected, filtered_count=0)


def run_discover(
    root: Path,
    date: str | None = None,
    sources_path: Path | None = None,
    limit: int = 80,
    min_stars: int | None = None,
    novelty_days: int | None = None,
) -> None:
    current_date = _normalize_date(date)
    today = date_type.fromisoformat(current_date)
    config = load_config(min_stars=min_stars, novelty_days=novelty_days)
    config_path = _resolve_sources_path(root, sources_path)
    github = _make_github_client()

    taste_seeds = _load_optional_manual_seeds(root, current_date)
    github_searches = load_github_search_sources(config_path)
    github_quota = _github_search_quota(limit, has_github_searches=bool(github_searches))
    curated_quota = max(limit - github_quota, 0)

    # Do NOT inject `github` into curated discovery: a None client preserves the curated
    # metadata throttle (DAILY_TOOL_DISCOVERY_GITHUB_DELAY_SECONDS). Tests use empty
    # curated sources, so curated discovery returns [] without any network call.
    candidates = discover_curated_candidates(
        load_curated_sources(config_path), discovered_at=current_date, limit=curated_quota,
    )
    candidates.extend(
        discover_github_search_candidates(
            github_searches, discovered_at=current_date, limit=github_quota, github_client=github,
        )
    )

    candidates = _dedupe_candidates(candidates)
    candidates = _exclude_manual_seed_urls(candidates, taste_seeds)

    # taste from manual seeds + positive feedback
    index = _build_candidate_index(root)
    signals = load_feedback_signals(root / "feedback.jsonl", index)
    taste_tags = {t for seed in taste_seeds for t in seed.tags} | set(signals.taste_tags)
    taste_kinds = {seed.kind for seed in taste_seeds} | set(signals.taste_kinds)
    candidates = _apply_taste_profile(candidates, taste_tags, taste_kinds)

    # trust tiers (annotated into the full inbox)
    candidates = [annotate_trust(c, assess_trust(c, today, config)) for c in candidates]
    _write_jsonl(root / "candidates" / f"{current_date}.jsonl", [c.to_dict() for c in candidates])

    rejected_count = sum(1 for c in candidates if c.metadata.get("trust_tier") == "reject")

    recent = load_recent_surfaced_ids(root / "history.jsonl", today, config.novelty_days)
    selectable = [
        c for c in candidates
        if c.metadata.get("trust_tier") != "reject"
        and c.id not in signals.suppressed_ids
        and c.id not in recent
    ]

    trusted = [c for c in selectable if c.metadata.get("trust_tier") == "trusted"]
    review = [c for c in selectable if c.metadata.get("trust_tier") == "review"]

    trusted, review, demoted = _enrich_finalists(trusted, review, github, today, config)
    rejected_count += demoted

    selected = select_daily_candidates(trusted, review, today=today)
    _write_briefing(root, current_date, selected, filtered_count=rejected_count)
    record_surfaced(root / "history.jsonl", current_date, selected)


def run_feedback(root: Path, date: str, candidate_id: str, verdict: str, value: str, note: str = "") -> None:
    feedback_date = _normalize_date(date)
    append_feedback(
        root / "feedback.jsonl",
        FeedbackRecord(date=feedback_date, candidate_id=candidate_id, verdict=verdict, value=value, note=note),
    )


def _enrich_finalists(trusted, review, github, today, config):
    """Deep-check publishers of the top finalists; demote suspicious ones to reject."""
    finalists = trusted[:6] + review[:6]
    demoted = 0
    bad_ids: set[str] = set()
    for candidate in finalists:
        login = str(candidate.metadata.get("owner_login") or "")
        if not login:
            continue
        try:
            user = github.get_user(login)
        except Exception:
            continue
        if publisher_is_suspicious(user, today, config):
            bad_ids.add(candidate.id)
            demoted += 1
    trusted = [c for c in trusted if c.id not in bad_ids]
    review = [c for c in review if c.id not in bad_ids]
    return trusted, review, demoted


def _build_candidate_index(root: Path) -> dict[str, Candidate]:
    index: dict[str, Candidate] = {}
    candidates_dir = root / "candidates"
    if not candidates_dir.exists():
        return index
    for path in sorted(candidates_dir.glob("*.jsonl")):
        for row in read_jsonl(path):
            try:
                candidate = Candidate.from_dict(row)
            except (KeyError, ValueError):
                continue
            index[candidate.id] = candidate
    return index


def _write_briefing(root: Path, current_date: str, selected, filtered_count: int) -> None:
    briefing_path = root / "briefings" / f"{current_date}.md"
    briefing_path.parent.mkdir(parents=True, exist_ok=True)
    briefing_path.write_text(
        render_briefing(current_date, selected, filtered_count=filtered_count), encoding="utf-8"
    )


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
    candidates: list[Candidate], taste_tags: set[str], taste_kinds: set[str]
) -> list[Candidate]:
    if not taste_tags and not taste_kinds:
        return candidates
    profiled: list[Candidate] = []
    for candidate in candidates:
        matching = sorted(set(candidate.tags) & taste_tags)
        if not matching:
            profiled.append(candidate)
            continue
        profiled.append(candidate.with_metadata(
            taste_profile_match=True,
            taste_profile_tags=matching,
            taste_profile_kind_match=candidate.kind in taste_kinds,
        ))
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
        raise ValueError(f"Invalid date: {raw_date!r}") from exc


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
    discover.add_argument("--min-stars", type=int, default=None)
    discover.add_argument("--novelty-days", type=int, default=None)

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
                root=args.root, date=args.date, sources_path=args.sources, limit=args.limit,
                min_stars=args.min_stars, novelty_days=args.novelty_days,
            )
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        return 0

    if args.command == "feedback":
        try:
            run_feedback(
                root=args.root, date=args.date, candidate_id=args.candidate_id,
                verdict=args.verdict, value=args.value, note=args.note,
            )
        except ValueError as exc:
            parser.error(str(exc))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
