import pytest

from daily_tool_discovery.feedback import FeedbackRecord, append_feedback
from daily_tool_discovery.jsonl_store import read_jsonl


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
