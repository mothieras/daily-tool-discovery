from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from daily_tool_discovery.jsonl_store import append_jsonl


FeedbackVerdict = Literal["tried", "saved", "ignored"]
FEEDBACK_VERDICTS: tuple[FeedbackVerdict, ...] = ("tried", "saved", "ignored")


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
