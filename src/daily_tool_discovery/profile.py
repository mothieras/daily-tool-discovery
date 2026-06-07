from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from daily_tool_discovery.config import TrustConfig, load_config
from daily_tool_discovery.curated_sources import (
    CuratedSource,
    GitHubSearchSource,
    curated_source_from_row,
    github_search_from_row,
)


@dataclass(frozen=True)
class Category:
    name: str
    weight: int
    signal_tags: tuple[str, ...]
    sources: tuple[CuratedSource, ...] = ()
    searches: tuple[GitHubSearchSource, ...] = ()


@dataclass(frozen=True)
class RecommendConfig:
    taste_max_points: int = 12
    relevance_max_points: int = 24
    relevance_tag_points: int = 4
    relevance_tags_per_category_cap: int = 3
    learn_last_n_saves: int = 20
    cold_start_min_saves: int = 5
    taste_points_per_tag: int = 6
    explore_slots: int = 1


@dataclass(frozen=True)
class Profile:
    name: str
    categories: tuple[Category, ...]
    trust: TrustConfig
    recommend: RecommendConfig
    deny: tuple[str, ...]


def resolve_profile_path(root: Path, profile_path: Path | None = None) -> Path:
    if profile_path is not None:
        return profile_path
    configured = root / "config" / "profile.toml"
    if configured.exists():
        return configured
    return root / "config" / "profile.example.toml"


def load_profile(path: Path, *, min_stars: int | None = None, novelty_days: int | None = None) -> Profile:
    if not path.exists():
        raise FileNotFoundError(f"profile not found: {path}")
    payload = tomllib.loads(path.read_text(encoding="utf-8"))

    categories: list[Category] = []
    for row in payload.get("category", []):
        name = str(row["name"])
        categories.append(
            Category(
                name=name,
                weight=int(row.get("weight", 1)),
                signal_tags=tuple(str(t) for t in row.get("signal_tags", [])),
                sources=tuple(curated_source_from_row(s, name) for s in row.get("source", [])),
                searches=tuple(github_search_from_row(s, name) for s in row.get("search", [])),
            )
        )

    trust = _build_trust(payload.get("trust", {}), min_stars=min_stars, novelty_days=novelty_days)
    rec = _build_recommend(payload.get("recommend", {}))
    deny = tuple(str(p) for p in payload.get("lists", {}).get("deny", []))
    name = str(payload.get("meta", {}).get("name", path.stem))
    return Profile(name=name, categories=tuple(categories), trust=trust, recommend=rec, deny=deny)


def _build_trust(tbl: dict, *, min_stars: int | None, novelty_days: int | None) -> TrustConfig:
    base = load_config(min_stars=min_stars, novelty_days=novelty_days)  # CLI > env > default
    return TrustConfig(
        min_stars=min_stars if min_stars is not None else int(tbl.get("min_stars", base.min_stars)),
        novelty_days=novelty_days if novelty_days is not None else int(tbl.get("novelty_days", base.novelty_days)),
        new_repo_days=int(tbl.get("new_repo_days", base.new_repo_days)),
        stale_months=int(tbl.get("stale_months", base.stale_months)),
    )


def _build_recommend(tbl: dict) -> RecommendConfig:
    defaults = RecommendConfig()
    return RecommendConfig(
        taste_max_points=int(tbl.get("taste_max_points", defaults.taste_max_points)),
        relevance_max_points=int(tbl.get("relevance_max_points", defaults.relevance_max_points)),
        relevance_tag_points=int(tbl.get("relevance_tag_points", defaults.relevance_tag_points)),
        relevance_tags_per_category_cap=int(tbl.get("relevance_tags_per_category_cap", defaults.relevance_tags_per_category_cap)),
        learn_last_n_saves=int(tbl.get("learn_last_n_saves", defaults.learn_last_n_saves)),
        cold_start_min_saves=int(tbl.get("cold_start_min_saves", defaults.cold_start_min_saves)),
        taste_points_per_tag=int(tbl.get("taste_points_per_tag", defaults.taste_points_per_tag)),
        explore_slots=int(tbl.get("explore_slots", defaults.explore_slots)),
    )
