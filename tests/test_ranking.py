from datetime import date

from daily_tool_discovery.models import Candidate
from daily_tool_discovery.ranking import (
    rank_candidates,
    select_from_pool,
    select_daily_candidates,
)

TODAY = date(2026, 6, 7)


def _c(cid, kind="agent-dev-tool", tags=("agent", "mcp", "cli"), **md):
    return Candidate(
        id=cid, name=cid, url=f"https://github.com/{cid}", source="github_search:x",
        summary="s", tags=list(tags), kind=kind, discovered_at="2026-06-07", metadata=md,
    )


def test_keyword_stuffed_zero_star_never_becomes_try():
    spam = _c("github:Bot/spam", stars=0, forks=0, pushed_at="2026-06-06T00:00:00Z")
    real = _c("github:real/tool", stars=800, forks=120, pushed_at="2026-06-01T00:00:00Z")
    selected = select_daily_candidates(trusted=[real], review=[spam], today=TODAY)
    by_id = {c.id: d for c, d in selected}
    assert by_id["github:Bot/spam"].action == "review"
    assert by_id["github:real/tool"].action in {"try", "save"}
    # spam never appears as try regardless of keyword match
    assert all(d.action != "try" for c, d in selected if c.id == "github:Bot/spam")


def test_freshness_bonus_only_with_stars():
    fresh_popular = _c("github:a/popular", stars=200, pushed_at="2026-06-06T00:00:00Z")
    fresh_lowstar = _c("github:b/lowstar", stars=2, pushed_at="2026-06-06T00:00:00Z")
    ranked = {r.candidate.id: r.score for r in rank_candidates([fresh_popular, fresh_lowstar], TODAY)}
    # recency adds to the popular one; the low-star one gets no recency bonus
    assert ranked["github:a/popular"] > ranked["github:b/lowstar"]


def test_stale_popular_penalized_relative_to_maintained():
    maintained = _c("github:a/m", stars=500, pushed_at="2026-05-01T00:00:00Z")
    stale = _c("github:b/s", stars=500, pushed_at="2020-01-01T00:00:00Z")
    ranked = {r.candidate.id: r.score for r in rank_candidates([maintained, stale], TODAY)}
    assert ranked["github:a/m"] > ranked["github:b/s"]


def test_select_from_pool_assigns_try_to_top_then_save():
    top = _c("github:a/top", stars=900, forks=200, pushed_at="2026-06-01T00:00:00Z")
    second = _c("github:b/second", stars=30, pushed_at="2026-05-01T00:00:00Z")
    selected = select_from_pool([second, top], today=TODAY, limit=3)
    assert selected[0][1].action == "try"
    assert selected[0][0].id == "github:a/top"
    assert selected[1][1].action == "save"


def test_review_bucket_capped_and_labeled():
    reviews = [_c(f"github:x/{i}", stars=1) for i in range(5)]
    selected = select_daily_candidates(trusted=[], review=reviews, today=TODAY, review_limit=2)
    review_items = [d for c, d in selected if d.action == "review"]
    assert len(review_items) == 2
