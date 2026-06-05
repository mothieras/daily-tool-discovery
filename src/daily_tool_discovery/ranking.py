from __future__ import annotations

from dataclasses import dataclass

from daily_tool_discovery.models import Candidate, CandidateDecision


HIGH_SIGNAL_TAGS = {
    "agent",
    "ai-coding",
    "mcp",
    "codex",
    "claude",
    "hermes",
    "tauri",
    "markdown",
    "obsidian",
    "cli",
    "local-first",
}


@dataclass(frozen=True)
class RankedCandidate:
    candidate: Candidate
    score: int
    reason: str


def rank_candidates(candidates: list[Candidate]) -> list[RankedCandidate]:
    ranked = [RankedCandidate(candidate, _score(candidate), _reason(candidate)) for candidate in candidates]
    return sorted(ranked, key=lambda item: item.score, reverse=True)


def select_daily_candidates(
    candidates: list[Candidate],
    limit: int = 3,
) -> list[tuple[Candidate, CandidateDecision]]:
    selected: list[tuple[Candidate, CandidateDecision]] = []
    for index, ranked in enumerate(rank_candidates(candidates)[:limit]):
        action = "try" if index == 0 and ranked.score >= 50 else "save"
        selected.append(
            (
                ranked.candidate,
                CandidateDecision(
                    candidate_id=ranked.candidate.id,
                    action=action,
                    score=ranked.score,
                    reason=ranked.reason,
                    caveat=_caveat(ranked.candidate),
                ),
            )
        )
    return selected


def _score(candidate: Candidate) -> int:
    score = 0
    if candidate.kind == "agent-dev-tool":
        score += 45
    elif candidate.kind == "open-source-small-tool":
        score += 30

    if candidate.metadata.get("manual_seed"):
        score += 35

    matching_tags = set(candidate.tags) & HIGH_SIGNAL_TAGS
    score += min(len(matching_tags) * 8, 32)

    stars = int(candidate.metadata.get("stars") or 0)
    if stars >= 3000:
        score += 12
    elif stars >= 500:
        score += 8
    elif stars >= 50:
        score += 4

    return min(score, 100)


def _reason(candidate: Candidate) -> str:
    if candidate.kind == "agent-dev-tool":
        return "Matches the main Agent/Dev tooling discovery line."
    if candidate.kind == "open-source-small-tool":
        return "Matches the open-source small-tool secondary line."
    return "Kept as a low-priority candidate for review."


def _caveat(candidate: Candidate) -> str:
    if candidate.kind == "other":
        return "Weak fit; inspect before saving."
    if not candidate.summary:
        return "Missing summary; verify the project before trying."
    return ""
