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
        min_stars: int = 0,
    ) -> list[Candidate]:
        effective_query = query
        if min_stars > 0 and "stars:" not in query:
            effective_query = f"{query} stars:>={min_stars}"
        params = urlencode(
            {"q": effective_query, "sort": "updated", "order": "desc", "per_page": str(per_page)}
        )
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

    def get_user(self, login: str) -> dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "daily-tool-discovery",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return self.transport.get_json(f"https://api.github.com/users/{login}", headers)

    def get_rate_limit(self) -> dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "daily-tool-discovery",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return self.transport.get_json("https://api.github.com/rate_limit", headers)


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
            "forks": int(item.get("forks_count") or 0),
            "open_issues": int(item.get("open_issues_count") or 0),
            "created_at": item.get("created_at"),
            "pushed_at": item.get("pushed_at"),
            "language": item.get("language"),
            "homepage": item.get("homepage"),
            "owner_login": str((item.get("owner") or {}).get("login") or ""),
            "owner_type": str((item.get("owner") or {}).get("type") or ""),
            "archived": bool(item.get("archived")),
            "is_fork": bool(item.get("fork")),
        },
    )
