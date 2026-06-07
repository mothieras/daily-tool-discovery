import pytest

from daily_tool_discovery.feedback import (
    FeedbackRecord,
    append_feedback,
    classify_feedback,
    load_feedback_signals,
)
from daily_tool_discovery.jsonl_store import read_jsonl
from daily_tool_discovery.models import Candidate


def test_feedback_record_serializes_to_json_dict():
    record = FeedbackRecord(
        date="2026-06-05",
        candidate_id="github:Achilng/floral-notepaper",
        verdict="tried",
        value="useful",
        note="Worth keeping as a local-first desktop utility.",
    )

    assert record.to_dict() == {
        "date": "2026-06-05",
        "candidate_id": "github:Achilng/floral-notepaper",
        "verdict": "tried",
        "value": "useful",
        "note": "Worth keeping as a local-first desktop utility.",
    }


def test_feedback_record_rejects_invalid_verdict():
    with pytest.raises(ValueError, match="invalid feedback verdict"):
        FeedbackRecord(
            date="2026-06-05",
            candidate_id="github:Achilng/floral-notepaper",
            verdict="skip",
            value="not-useful",
        )


def test_append_feedback_writes_jsonl(tmp_path):
    path = tmp_path / "feedback.jsonl"
    record = FeedbackRecord(
        date="2026-06-05",
        candidate_id="github:wxtsky/CodeIsland",
        verdict="saved",
        value="worth-tracking",
        note="Good workflow companion sample.",
    )

    append_feedback(path, record)

    assert read_jsonl(path) == [record.to_dict()]


def test_classify_feedback_polarity():
    assert classify_feedback("tried", "useful") == "positive"
    assert classify_feedback("tried", "not useful") == "negative"
    assert classify_feedback("tried", "blocked") == "negative"
    assert classify_feedback("saved", "worth tracking") == "positive"
    assert classify_feedback("saved", "duplicate") == "negative"
    assert classify_feedback("saved", "not relevant") == "negative"
    assert classify_feedback("ignored", "correct ignore") == "negative"
    assert classify_feedback("ignored", "false negative") == "positive"
    # unknown value -> verdict default
    assert classify_feedback("tried", "anything else") == "positive"
    assert classify_feedback("ignored", "whatever") == "negative"


def test_load_feedback_signals_suppresses_and_learns_taste(tmp_path):
    feedback_path = tmp_path / "feedback.jsonl"
    append_feedback(feedback_path, FeedbackRecord("2026-06-06", "github:bad/one", "ignored", "correct ignore"))
    append_feedback(feedback_path, FeedbackRecord("2026-06-06", "github:good/one", "tried", "useful"))
    index = {
        "github:good/one": Candidate(
            id="github:good/one", name="good/one", url="u", source="s", summary="",
            tags=["mcp", "agent"], kind="agent-dev-tool", discovered_at="2026-06-06",
        )
    }
    signals = load_feedback_signals(feedback_path, index)
    assert "github:bad/one" in signals.suppressed_ids
    assert "github:good/one" not in signals.suppressed_ids
    assert {"mcp", "agent"} <= signals.taste_tags
    assert "agent-dev-tool" in signals.taste_kinds


def test_load_feedback_signals_missing_file(tmp_path):
    signals = load_feedback_signals(tmp_path / "none.jsonl", {})
    assert signals.suppressed_ids == frozenset()
    assert signals.taste_tags == frozenset()
