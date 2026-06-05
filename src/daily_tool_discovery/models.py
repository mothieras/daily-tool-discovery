from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


CandidateKind = Literal["agent-dev-tool", "open-source-small-tool", "other"]
DecisionAction = Literal["try", "save", "ignore"]


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    url: str
    source: str
    summary: str
    tags: list[str]
    kind: CandidateKind
    discovered_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

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
