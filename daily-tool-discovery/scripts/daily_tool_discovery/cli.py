from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date as date_type
from pathlib import Path
from typing import Any, Iterable

from daily_tool_discovery.briefing import render_briefing
from daily_tool_discovery.curated_sources import (
    default_metadata_delay_seconds,
    discover_curated_candidates,
    discover_github_search_candidates,
)
from daily_tool_discovery.feedback import FeedbackRecord, append_feedback, load_feedback_signals
from daily_tool_discovery.github_client import GitHubClient
from daily_tool_discovery.history import load_recent_surfaced_ids, record_surfaced
from daily_tool_discovery.jsonl_store import read_jsonl
from daily_tool_discovery.lists import append_denylist, is_denied, load_denylist
from daily_tool_discovery.models import Candidate
from daily_tool_discovery.profile import (
    annotate_relevance, annotate_taste, learned_taste_tags, load_profile, resolve_profile_path,
)
from daily_tool_discovery.ranking import select_daily_candidates, select_from_pool
from daily_tool_discovery.seeds import load_manual_seeds
from daily_tool_discovery.trending import (
    TRENDING_SOURCES,
    discover_trending_candidates,
    gather_trending,
    render_browse_markdown,
)
from daily_tool_discovery.trust import annotate_trust, assess_trust, publisher_is_suspicious


class TokenError(Exception):
    """Raised when GITHUB_TOKEN is missing, invalid, or rate-limited."""


def _make_github_client() -> GitHubClient:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise TokenError(
            "GITHUB_TOKEN is not set. Without it, curated sources return 403 and "
            "the entire run produces garbage. Set it in ~/.hermes/.env or the environment."
        )
    client = GitHubClient(token=token)
    _verify_token_usable(client)
    return client


def _verify_token_usable(client: GitHubClient) -> None:
    """Check that the token works and has core rate limit remaining."""
    try:
        payload = client.get_rate_limit()
    except Exception as exc:
        raise TokenError(f"GitHub rate_limit check failed: {exc}") from exc
    core = payload.get("resources", {}).get("core", {})
    remaining = int(core.get("remaining") or 0)
    limit = int(core.get("limit") or 0)
    # limit=60 means unauthenticated — token not recognized
    if limit <= 60:
        raise TokenError(
            f"GitHub token appears invalid (rate limit={limit}, expected 5000). "
            "The API is treating requests as unauthenticated. Check if the token expired."
        )
    if remaining < 10:
        reset = core.get("reset")
        raise TokenError(
            f"GitHub core rate limit nearly exhausted ({remaining}/{limit} remaining). "
            f"Reset at epoch {reset}. Skipping this run rather than producing garbage."
        )


def run_dry_run(root: Path, date: str | None = None) -> None:
    current_date = _normalize_date(date)
    today = date_type.fromisoformat(current_date)
    seed_path = root / "seeds" / "manual.jsonl"
    if not seed_path.exists():
        raise FileNotFoundError(f"manual seed file not found: {seed_path}")
    candidates = load_manual_seeds(seed_path, discovered_at=current_date)
    _write_jsonl(root / "candidates" / f"{current_date}.jsonl", [c.to_dict() for c in candidates])
    selected = select_from_pool(candidates, today=today)
    _write_briefing(root, current_date, selected)


def run_discover(
    root: Path,
    date: str | None = None,
    profile_path: Path | None = None,
    limit: int = 80,
    min_stars: int | None = None,
    novelty_days: int | None = None,
    text_transport=None,
) -> None:
    current_date = _normalize_date(date)
    today = date_type.fromisoformat(current_date)
    profile = load_profile(resolve_profile_path(root, profile_path), min_stars=min_stars, novelty_days=novelty_days)
    github = _make_github_client()

    all_sources = [s for cat in profile.categories for s in cat.sources]
    all_searches = [s for cat in profile.categories for s in cat.searches]
    github_quota = _github_search_quota(limit, has_github_searches=bool(all_searches))
    curated_quota = max(limit - github_quota, 0)

    candidates = discover_curated_candidates(
        all_sources, discovered_at=current_date, limit=curated_quota,
        github_client=github, metadata_delay_seconds=default_metadata_delay_seconds(),
    )
    candidates.extend(
        discover_github_search_candidates(all_searches, discovered_at=current_date, limit=github_quota, github_client=github)
    )
    candidates.extend(_trending_candidates(github, current_date, profile, text_transport))

    taste_seeds = _load_optional_manual_seeds(root, current_date)
    candidates = _dedupe_candidates(candidates)
    candidates = _exclude_manual_seed_urls(candidates, taste_seeds)

    index = _build_candidate_index(root)
    fb = load_feedback_signals(root / "feedback.jsonl", index)
    taste_pool = (list(taste_seeds) + list(fb.recent_saved))[-profile.recommend.learn_last_n_saves:]
    learned = learned_taste_tags(taste_pool, profile.recommend)

    candidates = [annotate_taste(annotate_relevance(c, profile), learned, profile.recommend) for c in candidates]
    candidates = [annotate_trust(c, assess_trust(c, today, profile.trust)) for c in candidates]
    _write_jsonl(root / "candidates" / f"{current_date}.jsonl", [c.to_dict() for c in candidates])

    deny = load_denylist(root / "denylist.txt", profile.deny)
    filtered = _filtered_items(candidates)

    recent = load_recent_surfaced_ids(root / "history.jsonl", today, profile.trust.novelty_days)
    selectable = [
        c for c in candidates
        if c.metadata.get("trust_tier") != "reject"
        and not is_denied(c.id, deny)
        and c.id not in fb.suppressed_ids
        and c.id not in fb.saved_ids
        and c.id not in recent
    ]
    trusted = [c for c in selectable if c.metadata.get("trust_tier") == "trusted"]
    review = [c for c in selectable if c.metadata.get("trust_tier") == "review"]

    trusted, review, demoted = _enrich_finalists(trusted, review, github, today, profile)
    filtered.extend((c.name, "suspicious-publisher") for c in demoted)

    selected = select_daily_candidates(trusted, review, today=today,
                                       explore_slots=profile.recommend.explore_slots)
    _write_briefing(root, current_date, selected, filtered=filtered)
    record_surfaced(root / "history.jsonl", current_date, selected)


def run_browse(
    root: Path,
    *,
    source: str = "all",
    limit: int = 20,
    language: str | None = None,
    since: str | None = None,
    min_stars: int | None = None,
    date: str | None = None,
) -> str:
    """Raw, read-only Markdown snapshot of GitHub Trending.

    No trust tier, ranking, LLM, or briefing; no state is written. Requires a
    usable GITHUB_TOKEN (same TokenError / exit 78 as `discover`).
    """
    discovered_at = _normalize_date(date)
    github = _make_github_client()
    want = TRENDING_SOURCES if source == "all" else (source,)
    floor = _browse_floor(root, min_stars)
    grouped = gather_trending(
        github,
        discovered_at,
        want=want,
        limits={s: limit for s in want},
        min_stars=floor,
        language=language,
        since_days=_parse_since(since),
    )
    text = render_browse_markdown(discovered_at, grouped, order=want, min_stars=floor)
    print(text, end="")
    return text


def _trending_candidates(github, discovered_at, profile, text_transport=None) -> list[Candidate]:
    """Trending pool for the daily briefing — opt-in, bounded, and non-fatal.

    Off by default: trending only runs when the active profile enables it
    (``[trending]`` with ``enabled = true``). When disabled the source is
    skipped entirely — no scrape, no GitHub calls, no WARN lines.

    When enabled, a trending failure (HTML layout change, GitHub 5xx) must not
    sink the run, so it degrades to an empty list and the other sources carry
    the briefing. ``text_transport`` is injectable for tests; ``None`` uses the
    live transport.
    """
    if not profile.trending_enabled:
        return []
    try:
        return discover_trending_candidates(
            github,
            discovered_at,
            daily_limit=10,
            weekly_limit=10,
            new_repos_limit=10,
            fast_growing_limit=10,
            min_stars=profile.trust.min_stars,
            text_transport=text_transport,
        )
    except Exception as exc:
        print(f"WARN [trending]: skipped trending sources: {exc}", file=sys.stderr)
        return []


def _browse_floor(root: Path, override: int | None) -> int:
    if override is not None:
        return override
    try:
        return load_profile(resolve_profile_path(root)).trust.min_stars
    except Exception:
        return 50  # read-only default when no profile/state is present


def _parse_since(value: str | None) -> int | None:
    """Parse a lookback like '7d' / '2w' / '14' into days; None if unset/invalid."""
    if not value:
        return None
    raw = value.strip().lower()
    match = re.fullmatch(r"(\d+)\s*([dw]?)", raw)
    if not match:
        return None
    amount = int(match.group(1))
    return amount * 7 if match.group(2) == "w" else amount


def run_feedback(root: Path, date: str, candidate_id: str, verdict: str, value: str, note: str = "") -> None:
    append_feedback(root / "feedback.jsonl",
                    FeedbackRecord(date=_normalize_date(date), candidate_id=candidate_id,
                                   verdict=verdict, value=value, note=note))


def run_save(root: Path, candidate_id: str, note: str = "") -> None:
    append_feedback(root / "feedback.jsonl",
                    FeedbackRecord(date=date_type.today().isoformat(), candidate_id=candidate_id,
                                   verdict="saved", value="worth tracking", note=note))


def run_deny(root: Path, pattern: str) -> None:
    append_denylist(root / "denylist.txt", pattern)


def _enrich_finalists(trusted, review, github, today, profile):
    finalists = trusted[:6] + review[:6]
    demoted: list[Candidate] = []
    bad_ids: set[str] = set()
    for candidate in finalists:
        login = str(candidate.metadata.get("owner_login") or "")
        if not login:
            continue
        try:
            user = github.get_user(login)
        except Exception:
            continue
        if publisher_is_suspicious(user, today, profile.trust):
            bad_ids.add(candidate.id)
            demoted.append(candidate)
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


def _filtered_items(candidates) -> list[tuple[str, str]]:
    """Repos dropped by the trust gate, paired with a human-readable reason.

    Denylisted repos are deliberately excluded: `deny` means "never surfaced",
    so naming them here would re-surface what the user asked to forget.
    """
    items: list[tuple[str, str]] = []
    for c in candidates:
        if c.metadata.get("trust_tier") == "reject":
            flags = c.metadata.get("risk_flags") or []
            items.append((c.name, "+".join(str(f) for f in flags) if flags else "low-trust"))
    return items


def _write_briefing(root, current_date, selected, filtered=()) -> None:
    briefing_path = root / "briefings" / f"{current_date}.md"
    briefing_path.parent.mkdir(parents=True, exist_ok=True)
    briefing_path.write_text(render_briefing(current_date, selected, filtered=filtered), encoding="utf-8")


def _load_optional_manual_seeds(root, discovered_at) -> list[Candidate]:
    seed_path = root / "seeds" / "manual.jsonl"
    if not seed_path.exists():
        return []
    return load_manual_seeds(seed_path, discovered_at=discovered_at)


def _exclude_manual_seed_urls(candidates, taste_seeds) -> list[Candidate]:
    seed_urls = {_normalize_url(seed.url) for seed in taste_seeds}
    if not seed_urls:
        return candidates
    return [c for c in candidates if _normalize_url(c.url) not in seed_urls]


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


def _dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    unique: dict[str, Candidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.id.lower(), candidate)
    return list(unique.values())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily-tool-discovery")
    sub = parser.add_subparsers(dest="command", required=True)

    dry = sub.add_parser("dry-run", help="Run the local manual-seed briefing pipeline")
    dry.add_argument("--root", type=Path, default=Path.cwd())
    dry.add_argument("--date", default=None)

    disc = sub.add_parser("discover", help="Discover candidates using the active profile")
    disc.add_argument("--root", type=Path, default=Path.cwd())
    disc.add_argument("--date", default=None)
    disc.add_argument("--profile", type=Path, default=None)
    disc.add_argument("--limit", type=int, default=80)
    disc.add_argument("--min-stars", type=int, default=None)
    disc.add_argument("--novelty-days", type=int, default=None)

    br = sub.add_parser("browse", help="Raw Markdown snapshot of GitHub Trending (no trust/ranking/LLM)")
    br.add_argument("--root", type=Path, default=Path.cwd())
    br.add_argument("--source", choices=["daily", "weekly", "new", "fast-growing", "all"], default="all")
    br.add_argument("--limit", type=int, default=20)
    br.add_argument("--language", default=None)
    br.add_argument("--since", default=None, help="Lookback for new/fast-growing, e.g. 7d, 2w (default 30d/7d)")
    br.add_argument("--min-stars", type=int, default=None)
    br.add_argument("--date", default=None)

    fb = sub.add_parser("feedback", help="Append lightweight feedback for a candidate")
    fb.add_argument("--root", type=Path, default=Path.cwd())
    fb.add_argument("--date", required=True)
    fb.add_argument("--candidate-id", required=True)
    fb.add_argument("--verdict", choices=["tried", "saved", "ignored"], required=True)
    fb.add_argument("--value", required=True)
    fb.add_argument("--note", default="")

    sv = sub.add_parser("save", help="Save (bookmark) a candidate; gently biases future recs")
    sv.add_argument("--root", type=Path, default=Path.cwd())
    sv.add_argument("--candidate-id", required=True)
    sv.add_argument("--note", default="")

    dn = sub.add_parser("deny", help="Add an owner/repo glob to denylist.txt (never surfaced)")
    dn.add_argument("--root", type=Path, default=Path.cwd())
    dn.add_argument("--pattern", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    if argv == []:
        return 0
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "dry-run":
            run_dry_run(root=args.root, date=args.date)
        elif args.command == "discover":
            run_discover(root=args.root, date=args.date, profile_path=args.profile,
                         limit=args.limit, min_stars=args.min_stars, novelty_days=args.novelty_days)
        elif args.command == "browse":
            run_browse(root=args.root, source=args.source, limit=args.limit,
                       language=args.language, since=args.since, min_stars=args.min_stars,
                       date=args.date)
        elif args.command == "feedback":
            run_feedback(root=args.root, date=args.date, candidate_id=args.candidate_id,
                         verdict=args.verdict, value=args.value, note=args.note)
        elif args.command == "save":
            run_save(root=args.root, candidate_id=args.candidate_id, note=args.note)
        elif args.command == "deny":
            run_deny(root=args.root, pattern=args.pattern)
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except TokenError as exc:
        print(f"ERROR [token]: {exc}", file=sys.stderr)
        return 78  # EX_CONFIG: configuration error
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
