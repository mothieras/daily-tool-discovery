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
    trending_enabled: bool = False


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
    trending_enabled = bool(payload.get("trending", {}).get("enabled", False))
    return Profile(
        name=name, categories=tuple(categories), trust=trust, recommend=rec,
        deny=deny, trending_enabled=trending_enabled,
    )


def _build_trust(tbl: dict, *, min_stars: int | None, novelty_days: int | None) -> TrustConfig:
    base = load_config(min_stars=min_stars, novelty_days=novelty_days)  # CLI > env > default
    return TrustConfig(
        min_stars=min_stars if min_stars is not None else int(tbl.get("min_stars", base.min_stars)),
        novelty_days=novelty_days if novelty_days is not None else int(tbl.get("novelty_days", base.novelty_days)),
        new_repo_days=int(tbl.get("new_repo_days", base.new_repo_days)),
        active_days=int(tbl.get("active_days", base.active_days)),
        established_stars=int(tbl.get("established_stars", base.established_stars)),
        established_days=int(tbl.get("established_days", base.established_days)),
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


import re

from daily_tool_discovery.models import Candidate

# Split words on anything that is not an alphanumeric, '+', '#', or '-'. This keeps
# hyphenated compounds (e.g. "mcp-server") as a token AND, below, we also break them
# into their parts ("mcp", "server") so both whole-tag and word-level matches work.
_COMPOUND_RE = re.compile(r"[^a-z0-9+#-]+")


def relevance_signals(candidate: Candidate) -> set[str]:
    tokens = {str(t).lower() for t in candidate.tags}
    for text in (candidate.name, candidate.summary):
        for compound in _COMPOUND_RE.split(str(text).lower()):
            if not compound:
                continue
            tokens.add(compound)
            tokens.update(part for part in compound.split("-") if part)
    return tokens


def annotate_relevance(candidate: Candidate, profile: Profile) -> Candidate:
    signals = relevance_signals(candidate)
    rec = profile.recommend
    matched_points = 0
    matched_categories: list[str] = []
    matched_tags: set[str] = set()
    for cat in profile.categories:
        matched = signals & {t.lower() for t in cat.signal_tags}
        if matched:
            matched_points += cat.weight * min(len(matched), rec.relevance_tags_per_category_cap) * rec.relevance_tag_points
            matched_categories.append(cat.name)
            matched_tags |= matched
    if matched_categories:
        points = min(matched_points, rec.relevance_max_points)
    else:
        # provenance floor: source category gives some relevance, but NOT a taste match
        prov = next((c for c in profile.categories
                     if c.name == candidate.metadata.get("category")), None)
        points = min(prov.weight * rec.relevance_tag_points, rec.relevance_max_points) if prov else 0
    return candidate.with_metadata(
        relevance_points=points,
        matched_categories=matched_categories,
        matched_tags=sorted(matched_tags),
        taste_matched=bool(matched_categories),   # real tag match only -> Explore stays non-empty
    )


def learned_taste_tags(saved_candidates: list[Candidate], recommend: RecommendConfig) -> set[str]:
    if len(saved_candidates) < recommend.cold_start_min_saves:
        return set()
    return {str(t).lower() for c in saved_candidates for t in c.tags}


def annotate_taste(candidate: Candidate, learned_tags: set[str], recommend: RecommendConfig) -> Candidate:
    if not learned_tags:
        return candidate
    hits = relevance_signals(candidate) & learned_tags
    if not hits:
        return candidate
    points = min(len(hits) * recommend.taste_points_per_tag, recommend.taste_max_points)
    return candidate.with_metadata(taste_points=points)
