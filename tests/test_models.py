from daily_tool_discovery.models import Candidate, CandidateDecision


def test_candidate_round_trips_to_json_dict():
    candidate = Candidate(
        id="github:Achilng/floral-notepaper",
        name="floral-notepaper",
        url="https://github.com/Achilng/floral-notepaper",
        source="github",
        summary="Lightweight Markdown sticky notes",
        tags=["tauri", "markdown", "local-first"],
        kind="open-source-small-tool",
        discovered_at="2026-06-05",
        metadata={"stars": 3500, "language": "TypeScript"},
    )

    restored = Candidate.from_dict(candidate.to_dict())

    assert restored == candidate


def test_candidate_decision_round_trips_to_json_dict():
    decision = CandidateDecision(
        candidate_id="github:wxtsky/CodeIsland",
        action="try",
        score=91,
        reason="Improves visibility into AI coding sessions.",
        caveat="macOS-specific workflow companion.",
    )

    restored = CandidateDecision.from_dict(decision.to_dict())

    assert restored == decision
