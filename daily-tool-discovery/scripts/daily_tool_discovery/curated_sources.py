from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from daily_tool_discovery.github_client import GitHubClient
from daily_tool_discovery.models import Candidate, CandidateKind


GITHUB_REPO_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:[)\]#\s/?]|$)"
)


class TextTransport(Protocol):
    def get_text(self, url: str) -> str:
        ...


class UrllibTextTransport:
    def get_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": "daily-tool-discovery"})
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")


@dataclass(frozen=True)
class CuratedSource:
    name: str
    url: str
    category: str = "other"


@dataclass(frozen=True)
class GitHubSearchSource:
    name: str
    query: str
    category: str = "other"
    per_page: int = 10
    min_stars: int = 20


def curated_source_from_row(row: dict, category: str) -> CuratedSource:
    if not isinstance(row, dict):
        raise ValueError(f"source must be a table, got {type(row).__name__}")
    try:
        return CuratedSource(name=str(row["name"]), url=str(row["url"]), category=category)
    except KeyError as exc:
        raise ValueError(f"source missing {exc.args[0]!r}") from exc


def github_search_from_row(row: dict, category: str) -> GitHubSearchSource:
    if not isinstance(row, dict):
        raise ValueError(f"github_search must be a table, got {type(row).__name__}")
    try:
        return GitHubSearchSource(
            name=str(row["name"]),
            query=str(row["query"]),
            category=category,
            per_page=int(row.get("per_page", 10)),
            min_stars=int(row.get("min_stars", 20)),
        )
    except KeyError as exc:
        raise ValueError(f"github_search missing {exc.args[0]!r}") from exc


def discover_curated_candidates(
    sources: list[CuratedSource],
    discovered_at: str,
    limit: int = 80,
    text_transport: TextTransport | None = None,
    github_client: GitHubClient | None = None,
    metadata_delay_seconds: float | None = None,
) -> list[Candidate]:
    if not sources or limit <= 0:
        return []

    text_client = text_transport or UrllibTextTransport()
    github = github_client or GitHubClient(token=os.environ.get("GITHUB_TOKEN"))
    delay = (
        metadata_delay_seconds
        if metadata_delay_seconds is not None
        else _metadata_delay_seconds(github_client)
    )
    candidates_by_id: dict[str, Candidate] = {}
    per_source_limit = max(1, (limit + len(sources) - 1) // len(sources))

    for source in sources:
        try:
            text = text_client.get_text(source.url)
        except OSError:
            continue

        added_from_source = 0
        for full_name in extract_github_repos(text):
            candidate = _candidate_from_repo(
                full_name=full_name,
                source=source,
                discovered_at=discovered_at,
                github_client=github,
            )
            if delay > 0:
                time.sleep(delay)
            before_count = len(candidates_by_id)
            candidates_by_id.setdefault(candidate.id.lower(), candidate)
            if len(candidates_by_id) > before_count:
                added_from_source += 1
            if len(candidates_by_id) >= limit:
                return list(candidates_by_id.values())
            if added_from_source >= per_source_limit:
                break

    return list(candidates_by_id.values())


def discover_github_search_candidates(
    searches: list[GitHubSearchSource],
    discovered_at: str,
    limit: int = 80,
    github_client: GitHubClient | None = None,
) -> list[Candidate]:
    github = github_client or GitHubClient(token=os.environ.get("GITHUB_TOKEN"))
    candidates_by_id: dict[str, Candidate] = {}

    for search in searches:
        try:
            candidates = github.search_repositories(
                query=search.query,
                discovered_at=discovered_at,
                kind=search.category,
                per_page=search.per_page,
                min_stars=search.min_stars,
            )
        except Exception:
            continue
        for candidate in candidates:
            candidate = Candidate(
                id=candidate.id,
                name=candidate.name,
                url=candidate.url,
                source=f"github_search:{search.name}",
                summary=candidate.summary,
                tags=candidate.tags,
                kind=candidate.kind,
                discovered_at=candidate.discovered_at,
                metadata=candidate.metadata,
            )
            candidates_by_id.setdefault(candidate.id.lower(), candidate)
            if len(candidates_by_id) >= limit:
                return list(candidates_by_id.values())

    return list(candidates_by_id.values())


def extract_github_repos(text: str) -> list[str]:
    repos: list[str] = []
    seen: set[str] = set()
    for match in GITHUB_REPO_RE.finditer(text):
        full_name = _clean_repo_name(match.group(1))
        if _is_curated_list_repo(full_name):
            continue
        key = full_name.lower()
        if key not in seen:
            seen.add(key)
            repos.append(full_name)
    return repos


def _candidate_from_repo(
    full_name: str,
    source: CuratedSource,
    discovered_at: str,
    github_client: GitHubClient,
) -> Candidate:
    source_name = f"curated:{source.name}"
    try:
        return github_client.get_repository(
            full_name=full_name,
            discovered_at=discovered_at,
            kind=source.category,
            source=source_name,
        )
    except Exception as exc:
        return Candidate(
            id=f"github:{full_name}",
            name=full_name,
            url=f"https://github.com/{full_name}",
            source=source_name,
            summary="",
            tags=[],
            kind=source.category,
            discovered_at=discovered_at,
            metadata={
                "metadata_error": True,
                "metadata_error_type": type(exc).__name__,
                **_metadata_error_details(exc),
            },
        )


def _clean_repo_name(value: str) -> str:
    return value.removesuffix(".git").strip("/")


def _is_curated_list_repo(full_name: str) -> bool:
    repo_name = full_name.rsplit("/", 1)[-1].lower()
    return repo_name == "awesome" or repo_name.startswith("awesome-")


def default_metadata_delay_seconds() -> float:
    """Per-repo self-throttle for metadata fetches, configurable via env."""
    raw_value = os.environ.get("DAILY_TOOL_DISCOVERY_GITHUB_DELAY_SECONDS", "0.25")
    try:
        return max(float(raw_value), 0.0)
    except ValueError:
        return 0.25


def _metadata_delay_seconds(github_client: GitHubClient | None) -> float:
    # Back-compat default: an injected client signals the caller owns rate
    # control, so don't add a delay unless one is requested explicitly.
    if github_client is not None:
        return 0.0
    return default_metadata_delay_seconds()


def _metadata_error_details(exc: Exception) -> dict[str, object]:
    if isinstance(exc, HTTPError):
        return {"metadata_error_status": exc.code}
    return {}
