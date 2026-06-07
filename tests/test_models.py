import pytest

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


def test_candidate_rejects_invalid_kind():
    with pytest.raises(ValueError):
        Candidate.from_dict(
            {
                "id": "github:example/tool",
                "name": "tool",
                "url": "https://github.com/example/tool",
                "source": "github",
                "summary": "Example tool",
                "tags": [],
                "kind": "invalid",
                "discovered_at": "2026-06-05",
            }
        )


def test_candidate_decision_rejects_invalid_action():
    with pytest.raises(ValueError):
        CandidateDecision.from_dict(
            {
                "candidate_id": "github:example/tool",
                "action": "invalid",
                "score": 10,
                "reason": "Example reason",
            }
        )


def test_candidate_is_isolated_from_external_mutation():
    tags = ["tauri"]
    metadata = {"stars": 3500}
    candidate = Candidate(
        id="github:Achilng/floral-notepaper",
        name="floral-notepaper",
        url="https://github.com/Achilng/floral-notepaper",
        source="github",
        summary="Lightweight Markdown sticky notes",
        tags=tags,
        kind="open-source-small-tool",
        discovered_at="2026-06-05",
        metadata=metadata,
    )

    tags.append("mutated")
    metadata["stars"] = 1

    assert candidate.to_dict()["tags"] == ["tauri"]
    assert candidate.to_dict()["metadata"] == {"stars": 3500}


def test_with_metadata_merges_and_returns_new_candidate():
    base = Candidate(
        id="github:a/b", name="a/b", url="https://github.com/a/b",
        source="curated:x", summary="s", tags=["cli"], kind="other",
        discovered_at="2026-06-07", metadata={"stars": 5},
    )
    updated = base.with_metadata(trust_tier="review", stars=5)
    assert updated is not base
    assert base.metadata.get("trust_tier") is None  # original untouched
    assert updated.metadata["trust_tier"] == "review"
    assert updated.metadata["stars"] == 5
    assert updated.tags == ("cli",)
