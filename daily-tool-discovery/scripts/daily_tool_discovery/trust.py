from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from daily_tool_discovery.config import TrustConfig
from daily_tool_discovery.models import Candidate

TrustTier = Literal["trusted", "review", "reject"]

# random word + random word + digits, e.g. "BlueElephant42"
_AUTO_LOGIN_RE = re.compile(r"^[A-Z][a-z]{2,}[A-Z][a-z]{2,}\d{2,}$")


@dataclass(frozen=True)
class TrustAssessment:
    tier: TrustTier
    risk_flags: tuple[str, ...]


def is_auto_generated_login(login: str) -> bool:
    return bool(_AUTO_LOGIN_RE.match(login or ""))


def _days_since(value: object, today: date) -> int | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    return (today - parsed).days


def assess_trust(candidate: Candidate, today: date, config: TrustConfig) -> TrustAssessment:
    md = candidate.metadata
    stars = int(md.get("stars") or 0)
    forks = int(md.get("forks") or 0)
    archived = bool(md.get("archived"))
    is_fork = bool(md.get("is_fork"))
    login = str(md.get("owner_login") or "")
    created_days = _days_since(md.get("created_at"), today)
    pushed_days = _days_since(md.get("pushed_at"), today)

    flags: list[str] = []
    auto = is_auto_generated_login(login)
    if auto:
        flags.append("auto-generated-username")
    brand_new = created_days is not None and created_days <= config.new_repo_days
    if brand_new:
        flags.append("brand-new-repo")
    no_community = stars == 0 and forks == 0
    if no_community:
        flags.append("no-community")
    if archived:
        flags.append("archived")
    if is_fork:
        flags.append("fork")

    # Active = pushed recently, with a tier by stars: small repos must be fresh
    # (a quiet month reads as abandoned), established repos get a longer window.
    active_window = config.established_days if stars >= config.established_stars else config.active_days
    active = pushed_days is not None and pushed_days <= active_window
    if pushed_days is not None and not active:
        flags.append("stale")

    if auto and brand_new and no_community:
        return TrustAssessment("reject", tuple(flags))

    if stars >= config.min_stars and not archived and active:
        return TrustAssessment("trusted", tuple(flags))

    return TrustAssessment("review", tuple(flags))


def publisher_is_suspicious(user: dict, today: date, config: TrustConfig) -> bool:
    created_days = _days_since(user.get("created_at"), today)
    public_repos = int(user.get("public_repos") or 0)
    followers = int(user.get("followers") or 0)
    return (
        created_days is not None
        and created_days <= config.new_repo_days
        and public_repos <= 2
        and followers == 0
    )


def annotate_trust(candidate: Candidate, assessment: TrustAssessment) -> Candidate:
    return candidate.with_metadata(
        trust_tier=assessment.tier,
        risk_flags=list(assessment.risk_flags),
    )
