from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from daily_tool_discovery.jsonl_store import append_jsonl, read_jsonl
from daily_tool_discovery.models import Candidate


FeedbackVerdict = Literal["tried", "saved", "ignored"]
FEEDBACK_VERDICTS: tuple[FeedbackVerdict, ...] = ("tried", "saved", "ignored")

_NEGATIVE_WORDS = ("not useful", "useless", "blocked", "not relevant", "duplicate", "correct ignore")
_POSITIVE_WORDS = ("useful", "worth tracking", "false negative")
_VERDICT_DEFAULT = {"tried": "positive", "saved": "positive", "ignored": "negative"}


@dataclass(frozen=True)
class FeedbackRecord:
    date: str
    candidate_id: str
    verdict: FeedbackVerdict
    value: str
    note: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in FEEDBACK_VERDICTS:
            raise ValueError(f"invalid feedback verdict: {self.verdict}")

    def to_dict(self) -> dict[str, str]:
        return {
            "date": self.date,
            "candidate_id": self.candidate_id,
            "verdict": self.verdict,
            "value": self.value,
            "note": self.note,
        }


def append_feedback(path: Path, record: FeedbackRecord) -> None:
    append_jsonl(path, [record.to_dict()])


def classify_feedback(verdict: str, value: str) -> str:
    text = (value or "").strip().lower()
    if any(word in text for word in _NEGATIVE_WORDS):
        return "negative"
    if any(word in text for word in _POSITIVE_WORDS):
        return "positive"
    return _VERDICT_DEFAULT.get(verdict, "neutral")


@dataclass(frozen=True)
class FeedbackSignals:
    suppressed_ids: frozenset[str]
    taste_tags: frozenset[str]
    taste_kinds: frozenset[str]


def load_feedback_signals(feedback_path: Path, candidate_index: dict[str, Candidate]) -> FeedbackSignals:
    suppressed: set[str] = set()
    tags: set[str] = set()
    kinds: set[str] = set()
    for row in read_jsonl(feedback_path):
        candidate_id = str(row.get("candidate_id", ""))
        if not candidate_id:
            continue
        polarity = classify_feedback(str(row.get("verdict", "")), str(row.get("value", "")))
        if polarity == "negative":
            suppressed.add(candidate_id)
        elif polarity == "positive":
            liked = candidate_index.get(candidate_id)
            if liked is not None:
                tags.update(liked.tags)
                kinds.add(liked.kind)
    return FeedbackSignals(frozenset(suppressed), frozenset(tags), frozenset(kinds))
