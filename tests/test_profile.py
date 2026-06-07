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
