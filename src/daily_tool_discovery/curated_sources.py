from __future__ import annotations

import os
import re
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from daily_tool_discovery.github_client import GitHubClient
from daily_tool_discovery.models import CANDIDATE_KINDS, Candidate, CandidateKind


GITHUB_REPO_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:[)\]#\s/?]|$)"
)
HIGH_SIGNAL_WORDS = ("agent", "mcp", "claude", "codex", "cli", "workflow", "obsidian")


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
    kind: CandidateKind = "other"


@dataclass(frozen=True)
class GitHubSearchSource:
    name: str
    query: str
    kind: CandidateKind
    per_page: int = 10


def load_curated_sources(path: Path) -> list[CuratedSource]:
    if not path.exists():
        raise FileNotFoundError(f"sources config not found: {path}")

    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("sources", [])
    if not isinstance(rows, list):
        raise ValueError(f"Invalid sources config at {path}: sources must be a list")

    sources: list[CuratedSource] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Invalid sources config at {path}: source #{index} must be a table")
        try:
            sources.append(
                CuratedSource(
                    name=str(row["name"]),
                    url=str(row["url"]),
                    kind=_parse_kind(row.get("kind", "other"), path, f"source #{index}"),
                )
            )
        except KeyError as exc:
            raise ValueError(
                f"Invalid sources config at {path}: source #{index} missing {exc.args[0]!r}"
            ) from exc
    return sources


def load_github_search_sources(path: Path) -> list[GitHubSearchSource]:
    if not path.exists():
        raise FileNotFoundError(f"sources config not found: {path}")

    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("github_search", [])
    if not isinstance(rows, list):
        raise ValueError(f"Invalid sources config at {path}: github_search must be a list")

    searches: list[GitHubSearchSource] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Invalid sources config at {path}: github_search #{index} must be a table")
        try:
            searches.append(
                GitHubSearchSource(
                    name=str(row["name"]),
                    query=str(row["query"]),
                    kind=_parse_kind(row.get("kind", "other"), path, f"github_search #{index}"),
                    per_page=int(row.get("per_page", 10)),
                )
            )
        except KeyError as exc:
            raise ValueError(
                f"Invalid sources config at {path}: github_search #{index} missing {exc.args[0]!r}"
            ) from exc
    return searches


def discover_curated_candidates(
    sources: list[CuratedSource],
    discovered_at: str,
    limit: int = 80,
    text_transport: TextTransport | None = None,
    github_client: GitHubClient | None = None,
) -> list[Candidate]:
    if not sources or limit <= 0:
        return []

    text_client = text_transport or UrllibTextTransport()
    github = github_client or GitHubClient(token=os.environ.get("GITHUB_TOKEN"))
    metadata_delay_seconds = _metadata_delay_seconds(github_client)
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
            if metadata_delay_seconds > 0:
                time.sleep(metadata_delay_seconds)
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
                kind=search.kind,
                per_page=search.per_page,
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
            kind=source.kind,
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
            kind=_fallback_kind(full_name, source.kind),
            discovered_at=discovered_at,
            metadata={
                "metadata_error": True,
                "metadata_error_type": type(exc).__name__,
                **_metadata_error_details(exc),
            },
        )


def _fallback_kind(full_name: str, default: CandidateKind) -> CandidateKind:
    lowered = full_name.lower()
    if default != "other":
        return default
    if any(word in lowered for word in HIGH_SIGNAL_WORDS):
        return "agent-dev-tool"
    return "open-source-small-tool"


def _clean_repo_name(value: str) -> str:
    return value.removesuffix(".git").strip("/")


def _is_curated_list_repo(full_name: str) -> bool:
    repo_name = full_name.rsplit("/", 1)[-1].lower()
    return repo_name == "awesome" or repo_name.startswith("awesome-")


def _parse_kind(value: object, path: Path, context: str) -> CandidateKind:
    kind = str(value)
    if kind not in CANDIDATE_KINDS:
        raise ValueError(f"Invalid sources config at {path}: {context} has invalid kind {kind!r}")
    return kind  # type: ignore[return-value]


def _metadata_delay_seconds(github_client: GitHubClient | None) -> float:
    if github_client is not None:
        return 0.0
    raw_value = os.environ.get("DAILY_TOOL_DISCOVERY_GITHUB_DELAY_SECONDS", "0.25")
    try:
        return max(float(raw_value), 0.0)
    except ValueError:
        return 0.25


def _metadata_error_details(exc: Exception) -> dict[str, object]:
    if isinstance(exc, HTTPError):
        return {"metadata_error_status": exc.code}
    return {}
