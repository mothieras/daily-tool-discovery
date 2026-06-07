from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TrustConfig:
    min_stars: int = 20
    novelty_days: int = 30
    new_repo_days: int = 30
    stale_months: int = 12


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
        stale_months=_int_env(env, "DAILY_TOOL_DISCOVERY_STALE_MONTHS", 12),
    )
