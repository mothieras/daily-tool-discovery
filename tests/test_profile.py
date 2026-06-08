from pathlib import Path

from daily_tool_discovery.config import TrustConfig
from daily_tool_discovery.profile import Profile, RecommendConfig, load_profile, resolve_profile_path


PROFILE_TOML = """
[meta]
name = "test-taste"

[[category]]
name = "agents"
weight = 2
signal_tags = ["mcp", "agent"]
  [[category.source]]
  name = "awesome-mcp"
  url = "https://raw/example/README.md"
  [[category.search]]
  name = "fresh"
  query = "topic:mcp created:>2026-03-01"
  min_stars = 50

[[category]]
name = "cli"
weight = 1
signal_tags = ["cli", "tui"]

[trust]
min_stars = 25
novelty_days = 14

[recommend]
explore_slots = 2
taste_max_points = 10

[lists]
deny = ["bad/*"]
"""


def _write(tmp_path) -> Path:
    p = tmp_path / "profile.toml"
    p.write_text(PROFILE_TOML, encoding="utf-8")
    return p


def test_load_profile_parses_categories_and_sources(tmp_path):
    prof = load_profile(_write(tmp_path))
    assert prof.name == "test-taste"
    assert [c.name for c in prof.categories] == ["agents", "cli"]
    agents = prof.categories[0]
    assert agents.weight == 2
    assert agents.signal_tags == ("mcp", "agent")
    assert agents.sources[0].url == "https://raw/example/README.md"
    assert agents.sources[0].category == "agents"      # injected
    assert agents.searches[0].min_stars == 50
    assert agents.searches[0].category == "agents"
    assert prof.categories[1].sources == ()            # no sources is fine


def test_load_profile_trust_merge_precedence(tmp_path):
    prof = load_profile(_write(tmp_path))
    # toml overrides env/default; defaults fill the rest
    assert prof.trust == TrustConfig(min_stars=25, novelty_days=14, new_repo_days=30, stale_months=12)


def test_load_profile_cli_overrides_toml(tmp_path):
    prof = load_profile(_write(tmp_path), min_stars=99)
    assert prof.trust.min_stars == 99   # CLI > toml


def test_load_profile_recommend_and_deny(tmp_path):
    prof = load_profile(_write(tmp_path))
    assert prof.recommend.explore_slots == 2
    assert prof.recommend.taste_max_points == 10
    assert prof.recommend.learn_last_n_saves == 20  # default
    assert prof.deny == ("bad/*",)


def test_resolve_profile_path_prefers_profile_then_example(tmp_path):
    (tmp_path / "config").mkdir()
    example = tmp_path / "config" / "profile.example.toml"
    example.write_text("[meta]\nname='x'\n", encoding="utf-8")
    assert resolve_profile_path(tmp_path) == example
    real = tmp_path / "config" / "profile.toml"
    real.write_text("[meta]\nname='y'\n", encoding="utf-8")
    assert resolve_profile_path(tmp_path) == real


from daily_tool_discovery.models import Candidate
from daily_tool_discovery.profile import (
    Category, Profile, RecommendConfig,
    annotate_relevance, annotate_taste, learned_taste_tags, relevance_signals,
)
from daily_tool_discovery.config import TrustConfig


def _profile(categories, recommend=None):
    return Profile(name="p", categories=tuple(categories), trust=TrustConfig(),
                   recommend=recommend or RecommendConfig(), deny=())


def _cand(tags=(), name="o/r", summary="", category="other"):
    return Candidate(id=f"github:{name}", name=name, url="u", source="github_search:x",
                     summary=summary, tags=list(tags), kind=category, discovered_at="2026-06-07",
                     metadata={"category": category})


def test_relevance_signals_tokenizes_tags_name_summary():
    c = _cand(tags=["MCP"], name="cool/mcp-server", summary="A Claude tool")
    sig = relevance_signals(c)
    assert "mcp" in sig and "server" in sig and "claude" in sig and "tool" in sig


def test_annotate_relevance_pure_tags_weighted_and_capped():
    prof = _profile([Category("agents", weight=2, signal_tags=("mcp", "agent"))])
    c = annotate_relevance(_cand(tags=["mcp", "agent"]), prof)
    # 2 matched tags * weight 2 * relevance_tag_points 4 = 16
    assert c.metadata["relevance_points"] == 16
    assert c.metadata["taste_matched"] is True
    assert "agents" in c.metadata["matched_categories"]
    assert c.metadata["matched_tags"] == ["agent", "mcp"]   # which tags hit, for the briefing reason


def test_annotate_relevance_provenance_is_floor_not_taste_match():
    prof = _profile([Category("agents", weight=2, signal_tags=("mcp",))])
    # no matching tokens, but came from the "agents" category source
    c = annotate_relevance(_cand(tags=[], name="x/y", summary="", category="agents"), prof)
    # provenance floor: weight 2 * relevance_tag_points 4 = 8 points...
    assert c.metadata["relevance_points"] == 8
    # ...but provenance alone does NOT make it "on-taste" (keeps it eligible for Explore)
    assert c.metadata["taste_matched"] is False
    assert c.metadata["matched_categories"] == []


def test_annotate_relevance_zero_when_nothing_matches():
    prof = _profile([Category("agents", weight=2, signal_tags=("mcp",))])
    c = annotate_relevance(_cand(tags=["unrelated"], name="x/y", category="other"), prof)
    assert c.metadata["relevance_points"] == 0
    assert c.metadata["taste_matched"] is False


def test_annotate_relevance_overall_cap():
    rec = RecommendConfig(relevance_max_points=10)
    prof = _profile([Category("a", 3, ("mcp", "agent", "cli"))], recommend=rec)
    c = annotate_relevance(_cand(tags=["mcp", "agent", "cli"]), prof)
    assert c.metadata["relevance_points"] == 10  # capped


def test_learned_taste_cold_start_returns_empty():
    rec = RecommendConfig(cold_start_min_saves=5)
    saved = [_cand(tags=["mcp"]) for _ in range(3)]
    assert learned_taste_tags(saved, rec) == set()


def test_learned_taste_collects_tags_when_above_floor():
    rec = RecommendConfig(cold_start_min_saves=2)
    saved = [_cand(tags=["mcp"]), _cand(tags=["tauri", "cli"])]
    assert learned_taste_tags(saved, rec) == {"mcp", "tauri", "cli"}


def test_annotate_taste_per_tag_and_max_cap():
    rec = RecommendConfig(taste_points_per_tag=6, taste_max_points=12)
    learned = {"mcp", "agent", "cli"}
    c = annotate_taste(_cand(tags=["mcp", "agent", "cli"]), learned, rec)
    assert c.metadata["taste_points"] == 12  # 3 hits * 6 = 18 -> capped 12


def test_annotate_taste_noop_when_no_learned_tags():
    c = annotate_taste(_cand(tags=["mcp"]), set(), RecommendConfig())
    assert "taste_points" not in c.metadata


def test_shipped_example_profile_loads():
    prof = load_profile(Path("daily-tool-discovery/templates/profile.example.toml"))
    names = [c.name for c in prof.categories]
    assert "agent-dev" in names
    agent = next(c for c in prof.categories if c.name == "agent-dev")
    assert any("mcp" in s.url or "mcp" in s.name for s in agent.sources)
    assert agent.searches  # has at least one search
    assert prof.trust.min_stars == 20
