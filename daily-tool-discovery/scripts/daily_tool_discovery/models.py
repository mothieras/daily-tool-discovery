from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal


CandidateKind = str  # free-form provenance label (a profile category name, or "other")
DecisionAction = Literal["try", "recommend", "review", "explore"]

DECISION_ACTIONS: tuple[DecisionAction, ...] = ("try", "recommend", "review", "explore")


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    url: str
    source: str
    summary: str
    tags: Sequence[str]
    kind: CandidateKind
    discovered_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "source": self.source,
            "summary": self.summary,
            "tags": list(self.tags),
            "kind": self.kind,
            "discovered_at": self.discovered_at,
            "metadata": dict(self.metadata),
        }

    def with_metadata(self, **extra: Any) -> "Candidate":
        merged = {**dict(self.metadata), **extra}
        return Candidate(
            id=self.id,
            name=self.name,
            url=self.url,
            source=self.source,
            summary=self.summary,
            tags=self.tags,
            kind=self.kind,
            discovered_at=self.discovered_at,
            metadata=merged,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Candidate":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            url=str(data["url"]),
            source=str(data["source"]),
            summary=str(data.get("summary", "")),
            tags=[str(tag) for tag in data.get("tags", [])],
            kind=data.get("kind", "other"),
            discovered_at=str(data["discovered_at"]),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class CandidateDecision:
    candidate_id: str
    action: DecisionAction
    score: int
    reason: str
    caveat: str = ""

    def __post_init__(self) -> None:
        if self.action not in DECISION_ACTIONS:
            raise ValueError(f"invalid decision action: {self.action}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "action": self.action,
            "score": self.score,
            "reason": self.reason,
            "caveat": self.caveat,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateDecision":
        return cls(
            candidate_id=str(data["candidate_id"]),
            action=data["action"],
            score=int(data["score"]),
            reason=str(data["reason"]),
            caveat=str(data.get("caveat", "")),
        )
