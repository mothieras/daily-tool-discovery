from datetime import date

from daily_tool_discovery.models import Candidate
from daily_tool_discovery.ranking import (
    rank_candidates, select_from_pool, select_daily_candidates,
)

TODAY = date(2026, 6, 7)


def _c(cid, taste_matched=True, **md):
    md.setdefault("relevance_points", 16 if taste_matched else 0)
    md["taste_matched"] = taste_matched
    return Candidate(id=cid, name=cid, url=f"https://github.com/{cid}", source="github_search:x",
                     summary="s", tags=[], kind="agents", discovered_at="2026-06-07", metadata=md)


def test_zero_star_review_never_becomes_try():
    spam = _c("github:Bot/spam", stars=0, forks=0, relevance_points=24)
    real = _c("github:real/tool", stars=800, forks=120, pushed_at="2026-06-01T00:00:00Z")
    selected = select_daily_candidates(trusted=[real], review=[spam], today=TODAY)
    by_id = {c.id: d for c, d in selected}
    assert by_id["github:Bot/spam"].action == "review"
    assert all(d.action != "try" for c, d in selected if c.id == "github:Bot/spam")


def test_score_reads_relevance_and_taste_metadata():
    high = _c("github:a/high", stars=30, relevance_points=24, taste_points=12,
              pushed_at="2026-06-01T00:00:00Z")
    low = _c("github:b/low", stars=30, relevance_points=0, taste_points=0,
             pushed_at="2026-06-01T00:00:00Z")
    ranked = {r.candidate.id: r.score for r in rank_candidates([high, low], TODAY)}
    assert ranked["github:a/high"] > ranked["github:b/low"]


def test_freshness_bonus_only_with_stars():
    pop = _c("github:a/p", stars=200, pushed_at="2026-06-06T00:00:00Z")
    lowstar = _c("github:b/l", stars=2, pushed_at="2026-06-06T00:00:00Z")
    ranked = {r.candidate.id: r.score for r in rank_candidates([pop, lowstar], TODAY)}
    assert ranked["github:a/p"] > ranked["github:b/l"]


def test_select_from_pool_try_then_save():
    top = _c("github:a/top", stars=900, forks=200, relevance_points=24,
             pushed_at="2026-06-01T00:00:00Z")
    second = _c("github:b/sec", stars=25, pushed_at="2026-05-01T00:00:00Z")
    sel = select_from_pool([second, top], today=TODAY, limit=3)
    assert sel[0][1].action == "try" and sel[0][0].id == "github:a/top"
    assert sel[1][1].action == "recommend"


def test_reason_names_matched_tags():
    c = _c("github:a/x", relevance_points=16, matched_categories=["agent-dev"],
           matched_tags=["agent", "mcp"], pushed_at="2026-06-01T00:00:00Z")
    ranked = {r.candidate.id: r.reason for r in rank_candidates([c], TODAY)}
    assert ranked["github:a/x"] == "Matches your 'agent-dev' interest (agent, mcp)."


def test_review_caveat_reflects_reason_not_just_community():
    stale = _c("github:a/stale", risk_flags=["stale"])
    archived = _c("github:b/arch", risk_flags=["archived", "stale"])  # archived wins
    lowstar = _c("github:c/tiny", risk_flags=["no-community"])
    sel = select_daily_candidates(trusted=[], review=[stale, archived, lowstar],
                                  today=TODAY, review_limit=3)
    cav = {c.id: d.caveat.lower() for c, d in sel}
    assert "not updated recently" in cav["github:a/stale"]
    assert "archived" in cav["github:b/arch"]
    assert "community" in cav["github:c/tiny"]


def test_explore_picks_off_taste_trusted_candidate():
    on = _c("github:a/on", stars=900, taste_matched=True, relevance_points=24,
            pushed_at="2026-06-01T00:00:00Z")
    off = _c("github:b/off", stars=500, taste_matched=False, relevance_points=0,
             pushed_at="2026-06-01T00:00:00Z")
    sel = select_daily_candidates(trusted=[on, off], review=[], today=TODAY,
                                  try_save_limit=1, explore_slots=1)
    actions = {c.id: d.action for c, d in sel}
    assert actions["github:b/off"] == "explore"
    assert actions["github:a/on"] in {"try", "recommend"}


def test_explore_empty_when_no_off_taste():
    on = _c("github:a/on", stars=900, taste_matched=True, pushed_at="2026-06-01T00:00:00Z")
    sel = select_daily_candidates(trusted=[on], review=[], today=TODAY, explore_slots=1)
    assert all(d.action != "explore" for c, d in sel)
