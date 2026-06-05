import pytest

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


def test_render_briefing_rejects_mismatched_decision_candidate_id():
    candidate = Candidate(
        id="github:example/tool",
        name="example/tool",
        url="https://github.com/example/tool",
        source="github",
        summary="Example tool",
        tags=[],
        kind="other",
        discovered_at="2026-06-05",
    )
    decision = CandidateDecision(
        candidate_id="github:other/tool",
        action="save",
        score=40,
        reason="Wrong join.",
    )

    with pytest.raises(ValueError, match="decision candidate_id .* does not match candidate id"):
        render_briefing("2026-06-05", [(candidate, decision)])


def test_render_briefing_normalizes_free_form_fields_to_single_lines():
    candidate = Candidate(
        id="github:example/messy",
        name="example/messy\n## injected heading",
        url="https://github.com/example/messy\n- injected link item",
        source="github",
        summary="Example tool",
        tags=[],
        kind="other",
        discovered_at="2026-06-05",
    )
    decision = CandidateDecision(
        candidate_id=candidate.id,
        action="try",
        score=70,
        reason="Useful for notes.\n## injected reason heading",
        caveat="Needs local review.\n- injected caveat item",
    )

    markdown = render_briefing("2026-06-05", [(candidate, decision)])
    lines = markdown.splitlines()

    assert "### example/messy ## injected heading" in lines
    assert "- Link: https://github.com/example/messy - injected link item" in lines
    assert "- Type: other" in lines
    assert "- Why it matters: Useful for notes. ## injected reason heading" in lines
    assert "- Risk or caveat: Needs local review. - injected caveat item" in lines
    assert "## injected heading" not in lines
    assert "- injected link item" not in lines
    assert "## injected reason heading" not in lines
    assert "- injected caveat item" not in lines
