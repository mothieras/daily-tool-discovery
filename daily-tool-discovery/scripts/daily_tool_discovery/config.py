from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TrustConfig:
    min_stars: int = 20
    novelty_days: int = 30
    new_repo_days: int = 30
    active_days: int = 62           # repos below `established_stars` must be pushed within this (~2 months)
    established_stars: int = 500    # at/above this many stars, the relaxed window applies
    established_days: int = 150     # established repos may be this stale and still count as active (~5 months)


def _int_env(env: dict[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_config(
    env: dict[str, str] | None = None,
    *,
    min_stars: int | None = None,
    novelty_days: int | None = None,
) -> TrustConfig:
    env = os.environ if env is None else env
    return TrustConfig(
        min_stars=min_stars if min_stars is not None
        else _int_env(env, "DAILY_TOOL_DISCOVERY_MIN_STARS", 20),
        novelty_days=novelty_days if novelty_days is not None
        else _int_env(env, "DAILY_TOOL_DISCOVERY_NOVELTY_DAYS", 30),
        new_repo_days=_int_env(env, "DAILY_TOOL_DISCOVERY_NEW_REPO_DAYS", 30),
        active_days=_int_env(env, "DAILY_TOOL_DISCOVERY_ACTIVE_DAYS", 62),
        established_stars=_int_env(env, "DAILY_TOOL_DISCOVERY_ESTABLISHED_STARS", 500),
        established_days=_int_env(env, "DAILY_TOOL_DISCOVERY_ESTABLISHED_DAYS", 150),
    )
