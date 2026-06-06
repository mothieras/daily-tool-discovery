from __future__ import annotations

import json
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from daily_tool_discovery.models import Candidate, CandidateKind


class JsonTransport(Protocol):
    def get_json(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        ...


class UrllibJsonTransport:
    def get_json(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))


class GitHubClient:
    def __init__(self, transport: JsonTransport | None = None, token: str | None = None) -> None:
        self.transport = transport or UrllibJsonTransport()
        self.token = token

    def search_repositories(
        self,
        query: str,
        discovered_at: str,
        kind: CandidateKind,
        per_page: int = 10,
    ) -> list[Candidate]:
        params = urlencode({"q": query, "sort": "updated", "order": "desc", "per_page": str(per_page)})
        url = f"https://api.github.com/search/repositories?{params}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "daily-tool-discovery",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        payload = self.transport.get_json(url, headers)
        candidates: list[Candidate] = []
        for item in payload.get("items", []):
            candidates.append(candidate_from_github_payload(item, discovered_at, kind, source="github"))
        return candidates

    def get_repository(
        self,
        full_name: str,
        discovered_at: str,
        kind: CandidateKind,
        source: str,
    ) -> Candidate:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "daily-tool-discovery",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        payload = self.transport.get_json(f"https://api.github.com/repos/{full_name}", headers)
        return candidate_from_github_payload(payload, discovered_at, kind, source=source)


def candidate_from_github_payload(
    item: dict[str, Any],
    discovered_at: str,
    kind: CandidateKind,
    source: str,
) -> Candidate:
    full_name = str(item["full_name"])
    return Candidate(
        id=f"github:{full_name}",
        name=full_name,
        url=str(item["html_url"]),
        source=source,
        summary=str(item.get("description") or ""),
        tags=[str(topic) for topic in item.get("topics", [])],
        kind=kind,
        discovered_at=discovered_at,
        metadata={
            "stars": int(item.get("stargazers_count") or 0),
            "language": item.get("language"),
            "pushed_at": item.get("pushed_at"),
            "homepage": item.get("homepage"),
        },
    )
