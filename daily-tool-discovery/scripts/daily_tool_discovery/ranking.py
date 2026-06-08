from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from daily_tool_discovery.models import Candidate, CandidateDecision

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


def select_from_pool(candidates, today=None, limit=3) -> list[tuple[Candidate, CandidateDecision]]:
    selected = []
    for index, ranked in enumerate(rank_candidates(candidates, today)[:limit]):
        action = "try" if index == 0 and ranked.score >= TRY_SCORE_THRESHOLD else "recommend"
        selected.append((ranked.candidate, _decision(ranked, action)))
    return selected


def select_daily_candidates(
    trusted: list[Candidate],
    review: list[Candidate],
    today: date | None = None,
    try_save_limit: int = 3,
    review_limit: int = 3,
    explore_slots: int = 1,
) -> list[tuple[Candidate, CandidateDecision]]:
    # Partition trusted: on-taste feeds try/recommend; off-taste feeds the explore slot.
    on_taste = [c for c in trusted if c.metadata.get("taste_matched")]
    off_taste = [c for c in trusted if not c.metadata.get("taste_matched")]
    selected = list(select_from_pool(on_taste, today, try_save_limit))
    for ranked in rank_candidates(review, today)[:review_limit]:
        selected.append((ranked.candidate, _decision(ranked, "review")))
    for ranked in rank_candidates(off_taste, today)[:explore_slots]:
        selected.append((ranked.candidate, _decision(ranked, "explore")))
    return selected


def _decision(ranked: RankedCandidate, action: str) -> CandidateDecision:
    return CandidateDecision(
        candidate_id=ranked.candidate.id, action=action, score=ranked.score,
        reason=ranked.reason, caveat=_caveat(ranked.candidate, action),
    )


def _score(candidate: Candidate, today: date | None = None) -> int:
    md = candidate.metadata
    stars = int(md.get("stars") or 0)
    forks = int(md.get("forks") or 0)
    issues = int(md.get("open_issues") or 0)
    score = 0

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

    score += int(md.get("relevance_points") or 0)   # profile relevance (capped at annotation)
    score += int(md.get("taste_points") or 0)        # learned taste (capped at annotation)

    if md.get("manual_seed"):
        score += 35
    if md.get("owner_type") == "Organization":
        score += 4
    if md.get("publisher_trusted"):
        score += 4

    return max(min(score, 100), 0)


def _sort_key(item: RankedCandidate) -> tuple[int, int, int, str, str]:
    c = item.candidate
    return (
        -item.score,
        -int(c.metadata.get("relevance_points") or 0),
        -int(c.metadata.get("stars") or 0),
        c.id,
        c.name,
    )


def _reason(candidate: Candidate) -> str:
    cats = candidate.metadata.get("matched_categories") or []
    if cats:
        tags = candidate.metadata.get("matched_tags") or []
        if tags:
            return f"Matches your '{cats[0]}' interest ({', '.join(str(t) for t in tags[:4])})."
        return f"Matches your '{cats[0]}' interest."
    return "Trust-vetted; outside your usual interests."


def _caveat(candidate: Candidate, action: str) -> str:
    if action == "review":
        flags = candidate.metadata.get("risk_flags") or []
        if "archived" in flags:
            return "Archived — no longer maintained; audit before relying on it."
        if "stale" in flags:
            return "Not updated recently — verify it's still maintained before relying on it."
        return "Low community signal — audit before running; do not run blindly."
    if action == "explore":
        return "Outside your usual interests — included on purpose; skim it."
    if not candidate.summary:
        return "Missing summary; verify the project before trying."
    return ""
