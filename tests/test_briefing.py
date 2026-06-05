from daily_tool_discovery.briefing import render_briefing
from daily_tool_discovery.models import Candidate, CandidateDecision


def test_render_briefing_groups_try_and_save_items():
    candidate = Candidate(
        id="github:Achilng/floral-notepaper",
        name="Achilng/floral-notepaper",
        url="https://github.com/Achilng/floral-notepaper",
        source="github",
        summary="Lightweight Markdown sticky notes",
        tags=["tauri", "markdown"],
        kind="open-source-small-tool",
        discovered_at="2026-06-05",
        metadata={"stars": 3500},
    )
    decision = CandidateDecision(
        candidate_id=candidate.id,
        action="try",
        score=80,
        reason="Matches local-first small-tool taste.",
        caveat="Check release package for your OS.",
    )

    markdown = render_briefing("2026-06-05", [(candidate, decision)])

    assert "# Daily Tool Discovery Briefing - 2026-06-05" in markdown
    assert "## Try Today" in markdown
    assert "### Achilng/floral-notepaper" in markdown
    assert "- 15-minute trial:" in markdown
    assert "## Save" in markdown
    assert "No saved items today." in markdown
