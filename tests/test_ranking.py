from daily_tool_discovery.models import Candidate
from daily_tool_discovery.ranking import rank_candidates, select_daily_candidates


def candidate(id, kind, tags, stars=0, manual=False):
    return Candidate(
        id=id,
        name=id,
        url=f"https://example.com/{id}",
        source="manual" if manual else "github",
        summary="",
        tags=tags,
        kind=kind,
        discovered_at="2026-06-05",
        metadata={"stars": stars, "manual_seed": manual},
    )


def test_rank_candidates_prefers_agent_dev_and_manual_seeds():
    ranked = rank_candidates(
        [
            candidate("generic", "other", ["ai"], stars=10000),
            candidate("codeisland", "agent-dev-tool", ["agent", "ai-coding"], stars=50, manual=True),
            candidate("floral", "open-source-small-tool", ["tauri", "markdown"], stars=3500),
        ]
    )

    assert [item.candidate.id for item in ranked] == ["codeisland", "floral", "generic"]
    assert ranked[0].score > ranked[1].score


def test_select_daily_candidates_caps_output_at_three():
    selected = select_daily_candidates(
        [
            candidate("a", "agent-dev-tool", ["agent"], stars=10),
            candidate("b", "agent-dev-tool", ["mcp"], stars=10),
            candidate("c", "open-source-small-tool", ["tauri"], stars=10),
            candidate("d", "other", ["marketing"], stars=9999),
        ],
        limit=3,
    )

    assert len(selected) == 3
    assert [decision.action for _, decision in selected] == ["try", "save", "save"]


def test_rank_candidates_breaks_equal_scores_deterministically():
    first = [
        candidate("alpha", "agent-dev-tool", ["agent"], stars=10),
        candidate("beta", "agent-dev-tool", ["mcp"], stars=10),
    ]
    second = list(reversed(first))

    assert [item.candidate.id for item in rank_candidates(first)] == ["alpha", "beta"]
    assert [item.candidate.id for item in rank_candidates(second)] == ["alpha", "beta"]


def test_select_daily_candidates_chooses_same_try_candidate_for_reversed_input():
    first = [
        candidate("alpha", "agent-dev-tool", ["agent"], stars=10),
        candidate("beta", "agent-dev-tool", ["mcp"], stars=10),
    ]
    second = list(reversed(first))

    first_selected = select_daily_candidates(first, limit=2)
    second_selected = select_daily_candidates(second, limit=2)

    assert [(candidate.id, decision.action) for candidate, decision in first_selected] == [
        ("alpha", "try"),
        ("beta", "save"),
    ]
    assert [(candidate.id, decision.action) for candidate, decision in second_selected] == [
        ("alpha", "try"),
        ("beta", "save"),
    ]
