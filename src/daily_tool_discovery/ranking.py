from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from daily_tool_discovery.models import Candidate, CandidateDecision


HIGH_SIGNAL_TAGS = {
    "agent", "ai-coding", "mcp", "codex", "claude", "hermes",
    "tauri", "markdown", "obsidian", "cli", "local-first",
}

KIND_PRIORITY = {"agent-dev-tool": 2, "open-source-small-tool": 1, "other": 0}

TRY_SCORE_THRESHOLD = 45


@dataclass(frozen=True)
class RankedCandidate:
    candidate: Candidate
    score: int
    reason: str


def _days_since(value: object, today: date) -> int | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    return (today - parsed).days


def rank_candidates(candidates: list[Candidate], today: date | None = None) -> list[RankedCandidate]:
    ranked = [RankedCandidate(c, _score(c, today), _reason(c)) for c in candidates]
    return sorted(ranked, key=_sort_key)


def select_from_pool(
    candidates: list[Candidate], today: date | None = None, limit: int = 3
) -> list[tuple[Candidate, CandidateDecision]]:
    selected: list[tuple[Candidate, CandidateDecision]] = []
    for index, ranked in enumerate(rank_candidates(candidates, today)[:limit]):
        action = "try" if index == 0 and ranked.score >= TRY_SCORE_THRESHOLD else "save"
        selected.append((ranked.candidate, _decision(ranked, action)))
    return selected


def select_daily_candidates(
    trusted: list[Candidate],
    review: list[Candidate],
    today: date | None = None,
    try_save_limit: int = 3,
    review_limit: int = 3,
) -> list[tuple[Candidate, CandidateDecision]]:
    selected = select_from_pool(trusted, today, try_save_limit)
    for ranked in rank_candidates(review, today)[:review_limit]:
        selected.append((ranked.candidate, _decision(ranked, "review")))
    return selected


def _decision(ranked: RankedCandidate, action: str) -> CandidateDecision:
    return CandidateDecision(
        candidate_id=ranked.candidate.id,
        action=action,
        score=ranked.score,
        reason=ranked.reason,
        caveat=_caveat(ranked.candidate, action),
    )


def _score(candidate: Candidate, today: date | None = None) -> int:
    md = candidate.metadata
    stars = int(md.get("stars") or 0)
    forks = int(md.get("forks") or 0)
    issues = int(md.get("open_issues") or 0)
    score = 0

    # Community block (dominant)
    if stars >= 3000:
        score += 30
    elif stars >= 500:
        score += 24
    elif stars >= 100:
        score += 18
    elif stars >= 20:
        score += 10

    if forks >= 200:
        score += 8
    elif forks >= 20:
        score += 4

    if issues >= 10:
        score += 3

    # Maintenance recency — only with real community
    if today is not None:
        days = _days_since(md.get("pushed_at"), today)
        if days is not None and stars >= 20:
            if days <= 90:
                score += 8
            elif days <= 365:
                score += 4
            elif days > 730:
                score -= 6
        elif days is not None and days > 730:
            score -= 6

    # Relevance block (capped; cannot win alone)
    if candidate.kind == "agent-dev-tool":
        score += 16
    elif candidate.kind == "open-source-small-tool":
        score += 10
    matching_tags = set(candidate.tags) & HIGH_SIGNAL_TAGS
    score += min(len(matching_tags) * 4, 16)

    # Taste
    if md.get("manual_seed"):
        score += 35
    if md.get("taste_profile_match"):
        score += 6
        if md.get("taste_profile_kind_match"):
            score += 3
        score += min(len(md.get("taste_profile_tags") or []) * 3, 9)

    # Publisher (finalists)
    if md.get("owner_type") == "Organization":
        score += 4
    if md.get("publisher_trusted"):
        score += 4

    return max(min(score, 100), 0)


def _sort_key(item: RankedCandidate) -> tuple[int, int, int, int, str, str]:
    c = item.candidate
    return (
        -item.score,
        -KIND_PRIORITY[c.kind],
        -int(bool(c.metadata.get("manual_seed"))),
        -int(c.metadata.get("stars") or 0),
        c.id,
        c.name,
    )


def _reason(candidate: Candidate) -> str:
    if candidate.kind == "agent-dev-tool":
        return "Matches the main Agent/Dev tooling discovery line."
    if candidate.kind == "open-source-small-tool":
        return "Matches the open-source small-tool secondary line."
    return "Kept as a low-priority candidate for review."


def _caveat(candidate: Candidate, action: str) -> str:
    if action == "review":
        return "Low community signal — audit before running; do not run blindly."
    if candidate.kind == "other":
        return "Weak fit; inspect before saving."
    if not candidate.summary:
        return "Missing summary; verify the project before trying."
    return ""
