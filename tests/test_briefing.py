import pytest

from daily_tool_discovery.briefing import render_briefing
from daily_tool_discovery.models import Candidate, CandidateDecision


def _pair(cid, action, **md):
    candidate = Candidate(
        id=cid, name=cid, url=f"https://github.com/{cid}", source="github",
        summary="s", tags=["cli"], kind="agent-dev-tool", discovered_at="2026-06-07",
        metadata=md,
    )
    decision = CandidateDecision(candidate_id=cid, action=action, score=70, reason="why",
                                 caveat="" if action != "review" else "audit it")
    return candidate, decision


def test_renders_three_buckets_and_filtered_count():
    selected = [
        _pair("github:a/try", "try", stars=900, forks=100, open_issues=5,
              pushed_at="2026-06-01T00:00:00Z", owner_login="alice", owner_type="User"),
        _pair("github:b/save", "save", stars=50, owner_login="bob"),
        _pair("github:c/review", "review", stars=2, owner_login="carol"),
    ]
    out = render_briefing("2026-06-07", selected, filtered_count=4)
    assert "## Try Today" in out
    assert "## Save" in out
    assert "## Review yourself" in out
    assert "Filtered 4 suspicious candidates." in out


def test_metric_line_present_for_each_item():
    selected = [
        _pair("github:a/try", "try", stars=900, forks=100, open_issues=5,
              pushed_at="2026-06-01T00:00:00Z", owner_login="alice", owner_type="User"),
    ]
    out = render_briefing("2026-06-07", selected)
    assert "900" in out and "forks" in out and "alice" in out


def test_review_item_carries_audit_caveat():
    out = render_briefing("2026-06-07", [_pair("github:c/review", "review", stars=2, owner_login="x")])
    assert "audit" in out.lower()


def test_mismatched_pair_raises():
    candidate = Candidate(id="github:a/b", name="a/b", url="u", source="s", summary="",
                          tags=[], kind="other", discovered_at="2026-06-07")
    bad = CandidateDecision(candidate_id="github:x/y", action="save", score=1, reason="r")
    with pytest.raises(ValueError):
        render_briefing("2026-06-07", [(candidate, bad)])


def test_renders_explore_section_with_note():
    selected = [_pair("github:x/explore", "explore", stars=400, owner_login="dave")]
    out = render_briefing("2026-06-07", selected)
    assert "## 🎲 Explore" in out
    assert "included on purpose" in out.lower() or "don't dismiss" in out.lower()
    assert "github:x/explore" in out or "x/explore" in out
