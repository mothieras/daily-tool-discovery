# Daily Tool Discovery MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dry-run capable server-side MVP that collects tool candidates, stores inspectable JSONL artifacts, ranks them against the desired taste profile, and renders a short daily Markdown briefing.

**Architecture:** Use a deterministic Python CLI for collection, normalization, JSONL storage, ranking, Markdown rendering, and feedback logging. Hermes integration is represented by an inspectable review prompt and decision file interface in v1, so the collector remains debuggable and the Hermes invocation contract can be added after the server interface is confirmed.

**Tech Stack:** Python 3.11+, standard library, pytest for tests, GitHub REST API/search endpoints via `urllib.request`.

---

## File Structure

- Create `pyproject.toml`: package metadata, pytest config, CLI entry point.
- Create `.gitignore`: ignore runtime artifacts, caches, virtualenvs.
- Create `src/daily_tool_discovery/__init__.py`: package marker and version.
- Create `src/daily_tool_discovery/models.py`: typed dataclasses and serialization helpers.
- Create `src/daily_tool_discovery/jsonl_store.py`: append/read JSONL storage utilities.
- Create `src/daily_tool_discovery/seeds.py`: manual seed loading and weighting.
- Create `src/daily_tool_discovery/github_client.py`: GitHub API client with injectable transport.
- Create `src/daily_tool_discovery/ranking.py`: deterministic fit scoring and selection.
- Create `src/daily_tool_discovery/briefing.py`: Markdown briefing renderer.
- Create `src/daily_tool_discovery/feedback.py`: lightweight feedback record serialization.
- Create `src/daily_tool_discovery/cli.py`: `dry-run` and `feedback` commands.
- Create `prompts/hermes-review.md`: Hermes review prompt template for explicit review integration.
- Create `config/sources.example.toml`: first-week source configuration example.
- Create `seeds/manual.example.jsonl`: sample seeds for CodeIsland and floral-notepaper.
- Create `tests/`: focused unit tests for each module.
- Modify `README.md`: usage and dry-run instructions.

## Task 1: Python Package Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/daily_tool_discovery/__init__.py`
- Test: `tests/test_package.py`

- [ ] **Step 1: Write the package smoke test**

Create `tests/test_package.py`:

```python
from daily_tool_discovery import __version__


def test_package_has_version():
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_package.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'daily_tool_discovery'`.

- [ ] **Step 3: Add package configuration**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "daily-tool-discovery"
version = "0.1.0"
description = "Daily tool discovery briefing workflow"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
daily-tool-discovery = "daily_tool_discovery.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `.gitignore`:

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
dist/
build/
*.egg-info/

data/
candidates/
briefings/
feedback.jsonl
```

Create `src/daily_tool_discovery/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python -m pytest tests/test_package.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .gitignore pyproject.toml src/daily_tool_discovery/__init__.py tests/test_package.py
git commit -m "chore: scaffold python package"
```

## Task 2: Candidate Models And Serialization

**Files:**
- Create: `src/daily_tool_discovery/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write model tests**

Create `tests/test_models.py`:

```python
from daily_tool_discovery.models import Candidate, CandidateDecision


def test_candidate_round_trips_to_json_dict():
    candidate = Candidate(
        id="github:Achilng/floral-notepaper",
        name="floral-notepaper",
        url="https://github.com/Achilng/floral-notepaper",
        source="github",
        summary="Lightweight Markdown sticky notes",
        tags=["tauri", "markdown", "local-first"],
        kind="open-source-small-tool",
        discovered_at="2026-06-05",
        metadata={"stars": 3500, "language": "TypeScript"},
    )

    restored = Candidate.from_dict(candidate.to_dict())

    assert restored == candidate


def test_candidate_decision_round_trips_to_json_dict():
    decision = CandidateDecision(
        candidate_id="github:wxtsky/CodeIsland",
        action="try",
        score=91,
        reason="Improves visibility into AI coding sessions.",
        caveat="macOS-specific workflow companion.",
    )

    restored = CandidateDecision.from_dict(decision.to_dict())

    assert restored == decision
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_models.py -q
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `daily_tool_discovery.models`.

- [ ] **Step 3: Implement models**

Create `src/daily_tool_discovery/models.py`:

```python
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
```

- [ ] **Step 4: Run model tests**

Run:

```bash
python -m pytest tests/test_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/daily_tool_discovery/models.py tests/test_models.py
git commit -m "feat: add candidate models"
```

## Task 3: JSONL Store And Manual Seeds

**Files:**
- Create: `src/daily_tool_discovery/jsonl_store.py`
- Create: `src/daily_tool_discovery/seeds.py`
- Create: `seeds/manual.example.jsonl`
- Test: `tests/test_jsonl_store.py`
- Test: `tests/test_seeds.py`

- [ ] **Step 1: Write JSONL and seed tests**

Create `tests/test_jsonl_store.py`:

```python
from daily_tool_discovery.jsonl_store import append_jsonl, read_jsonl


def test_append_and_read_jsonl(tmp_path):
    path = tmp_path / "items.jsonl"

    append_jsonl(path, [{"name": "CodeIsland"}, {"name": "floral-notepaper"}])

    assert read_jsonl(path) == [
        {"name": "CodeIsland"},
        {"name": "floral-notepaper"},
    ]


def test_read_missing_jsonl_returns_empty_list(tmp_path):
    assert read_jsonl(tmp_path / "missing.jsonl") == []
```

Create `tests/test_seeds.py`:

```python
from daily_tool_discovery.models import Candidate
from daily_tool_discovery.seeds import load_manual_seeds


def test_load_manual_seeds(tmp_path):
    path = tmp_path / "manual.jsonl"
    path.write_text(
        '{"name":"CodeIsland","url":"https://example.com/codeisland","summary":"Agent status panel","tags":["agent","macos"],"kind":"agent-dev-tool"}\n',
        encoding="utf-8",
    )

    seeds = load_manual_seeds(path, discovered_at="2026-06-05")

    assert seeds == [
        Candidate(
            id="manual:https://example.com/codeisland",
            name="CodeIsland",
            url="https://example.com/codeisland",
            source="manual",
            summary="Agent status panel",
            tags=["agent", "macos"],
            kind="agent-dev-tool",
            discovered_at="2026-06-05",
            metadata={"manual_seed": True},
        )
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_jsonl_store.py tests/test_seeds.py -q
```

Expected: FAIL with missing `jsonl_store` and `seeds` modules.

- [ ] **Step 3: Implement JSONL store**

Create `src/daily_tool_discovery/jsonl_store.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return rows
```

- [ ] **Step 4: Implement manual seeds**

Create `src/daily_tool_discovery/seeds.py`:

```python
from __future__ import annotations

from pathlib import Path

from daily_tool_discovery.jsonl_store import read_jsonl
from daily_tool_discovery.models import Candidate


def load_manual_seeds(path: Path, discovered_at: str) -> list[Candidate]:
    seeds: list[Candidate] = []
    for row in read_jsonl(path):
        url = str(row["url"])
        seeds.append(
            Candidate(
                id=f"manual:{url}",
                name=str(row["name"]),
                url=url,
                source="manual",
                summary=str(row.get("summary", "")),
                tags=[str(tag) for tag in row.get("tags", [])],
                kind=row.get("kind", "other"),
                discovered_at=discovered_at,
                metadata={"manual_seed": True},
            )
        )
    return seeds
```

Create `seeds/manual.example.jsonl`:

```jsonl
{"name":"CodeIsland","url":"https://www.sourcepulse.org/projects/27607032","summary":"AI coding agent session status panel for macOS-style workflow visibility.","tags":["agent","ai-coding","macos","workflow"],"kind":"agent-dev-tool"}
{"name":"floral-notepaper","url":"https://github.com/Achilng/floral-notepaper","summary":"Open-source Tauri Markdown sticky-note desktop utility.","tags":["tauri","markdown","desktop","local-first"],"kind":"open-source-small-tool"}
```

- [ ] **Step 5: Run JSONL and seed tests**

Run:

```bash
python -m pytest tests/test_jsonl_store.py tests/test_seeds.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/daily_tool_discovery/jsonl_store.py src/daily_tool_discovery/seeds.py tests/test_jsonl_store.py tests/test_seeds.py seeds/manual.example.jsonl
git commit -m "feat: add jsonl storage and manual seeds"
```

## Task 4: GitHub Candidate Collector

**Files:**
- Create: `src/daily_tool_discovery/github_client.py`
- Test: `tests/test_github_client.py`

- [ ] **Step 1: Write GitHub client tests with fake transport**

Create `tests/test_github_client.py`:

```python
import json

from daily_tool_discovery.github_client import GitHubClient


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def get_json(self, url, headers):
        self.urls.append(url)
        return self.payload


def test_search_repositories_normalizes_candidates():
    transport = FakeTransport(
        {
            "items": [
                {
                    "full_name": "Achilng/floral-notepaper",
                    "html_url": "https://github.com/Achilng/floral-notepaper",
                    "description": "Lightweight Markdown sticky notes",
                    "topics": ["tauri", "markdown", "note-taking"],
                    "stargazers_count": 3500,
                    "language": "TypeScript",
                    "pushed_at": "2026-05-21T00:00:00Z",
                }
            ]
        }
    )
    client = GitHubClient(transport=transport)

    candidates = client.search_repositories(
        query="topic:tauri markdown",
        discovered_at="2026-06-05",
        kind="open-source-small-tool",
    )

    assert candidates[0].id == "github:Achilng/floral-notepaper"
    assert candidates[0].name == "Achilng/floral-notepaper"
    assert candidates[0].kind == "open-source-small-tool"
    assert candidates[0].metadata["stars"] == 3500
    assert "topic%3Atauri+markdown" in transport.urls[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_github_client.py -q
```

Expected: FAIL with missing `daily_tool_discovery.github_client`.

- [ ] **Step 3: Implement GitHub client**

Create `src/daily_tool_discovery/github_client.py`:

```python
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
            full_name = str(item["full_name"])
            candidates.append(
                Candidate(
                    id=f"github:{full_name}",
                    name=full_name,
                    url=str(item["html_url"]),
                    source="github",
                    summary=str(item.get("description") or ""),
                    tags=[str(topic) for topic in item.get("topics", [])],
                    kind=kind,
                    discovered_at=discovered_at,
                    metadata={
                        "stars": int(item.get("stargazers_count") or 0),
                        "language": item.get("language"),
                        "pushed_at": item.get("pushed_at"),
                    },
                )
            )
        return candidates
```

- [ ] **Step 4: Run GitHub client test**

Run:

```bash
python -m pytest tests/test_github_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/daily_tool_discovery/github_client.py tests/test_github_client.py
git commit -m "feat: add github candidate collector"
```

## Task 5: Ranking And Selection

**Files:**
- Create: `src/daily_tool_discovery/ranking.py`
- Test: `tests/test_ranking.py`

- [ ] **Step 1: Write ranking tests**

Create `tests/test_ranking.py`:

```python
from daily_tool_discovery.models import Candidate
from daily_tool_discovery.ranking import rank_candidates, select_daily_candidates


def candidate(id, kind, tags, stars=0, manual=False):
    return Candidate(
        id=id,
        name=id,
        url=f"https://example.com/{id}",
        source="manual" if manual else "github",
        summary="",
        tags=tags,
        kind=kind,
        discovered_at="2026-06-05",
        metadata={"stars": stars, "manual_seed": manual},
    )


def test_rank_candidates_prefers_agent_dev_and_manual_seeds():
    ranked = rank_candidates(
        [
            candidate("generic", "other", ["ai"], stars=10000),
            candidate("codeisland", "agent-dev-tool", ["agent", "ai-coding"], stars=50, manual=True),
            candidate("floral", "open-source-small-tool", ["tauri", "markdown"], stars=3500),
        ]
    )

    assert [item.candidate.id for item in ranked] == ["codeisland", "floral", "generic"]
    assert ranked[0].score > ranked[1].score


def test_select_daily_candidates_caps_output_at_three():
    selected = select_daily_candidates(
        [
            candidate("a", "agent-dev-tool", ["agent"], stars=10),
            candidate("b", "agent-dev-tool", ["mcp"], stars=10),
            candidate("c", "open-source-small-tool", ["tauri"], stars=10),
            candidate("d", "other", ["marketing"], stars=9999),
        ],
        limit=3,
    )

    assert len(selected) == 3
    assert [decision.action for _, decision in selected] == ["try", "save", "save"]
```

- [ ] **Step 2: Run ranking tests to verify they fail**

Run:

```bash
python -m pytest tests/test_ranking.py -q
```

Expected: FAIL with missing `daily_tool_discovery.ranking`.

- [ ] **Step 3: Implement ranking**

Create `src/daily_tool_discovery/ranking.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from daily_tool_discovery.models import Candidate, CandidateDecision


HIGH_SIGNAL_TAGS = {
    "agent",
    "ai-coding",
    "mcp",
    "codex",
    "claude",
    "hermes",
    "tauri",
    "markdown",
    "obsidian",
    "cli",
    "local-first",
}


@dataclass(frozen=True)
class RankedCandidate:
    candidate: Candidate
    score: int
    reason: str


def rank_candidates(candidates: list[Candidate]) -> list[RankedCandidate]:
    ranked = [RankedCandidate(candidate, _score(candidate), _reason(candidate)) for candidate in candidates]
    return sorted(ranked, key=lambda item: item.score, reverse=True)


def select_daily_candidates(
    candidates: list[Candidate],
    limit: int = 3,
) -> list[tuple[Candidate, CandidateDecision]]:
    selected: list[tuple[Candidate, CandidateDecision]] = []
    for index, ranked in enumerate(rank_candidates(candidates)[:limit]):
        action = "try" if index == 0 and ranked.score >= 60 else "save"
        selected.append(
            (
                ranked.candidate,
                CandidateDecision(
                    candidate_id=ranked.candidate.id,
                    action=action,
                    score=ranked.score,
                    reason=ranked.reason,
                    caveat=_caveat(ranked.candidate),
                ),
            )
        )
    return selected


def _score(candidate: Candidate) -> int:
    score = 0
    if candidate.kind == "agent-dev-tool":
        score += 45
    elif candidate.kind == "open-source-small-tool":
        score += 30

    if candidate.metadata.get("manual_seed"):
        score += 35

    matching_tags = set(candidate.tags) & HIGH_SIGNAL_TAGS
    score += min(len(matching_tags) * 8, 32)

    stars = int(candidate.metadata.get("stars") or 0)
    if stars >= 3000:
        score += 12
    elif stars >= 500:
        score += 8
    elif stars >= 50:
        score += 4

    return min(score, 100)


def _reason(candidate: Candidate) -> str:
    if candidate.kind == "agent-dev-tool":
        return "Matches the main Agent/Dev tooling discovery line."
    if candidate.kind == "open-source-small-tool":
        return "Matches the open-source small-tool secondary line."
    return "Kept as a low-priority candidate for review."


def _caveat(candidate: Candidate) -> str:
    if candidate.kind == "other":
        return "Weak fit; inspect before saving."
    if not candidate.summary:
        return "Missing summary; verify the project before trying."
    return ""
```

- [ ] **Step 4: Run ranking tests**

Run:

```bash
python -m pytest tests/test_ranking.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/daily_tool_discovery/ranking.py tests/test_ranking.py
git commit -m "feat: add deterministic candidate ranking"
```

## Task 6: Markdown Briefing Renderer

**Files:**
- Create: `src/daily_tool_discovery/briefing.py`
- Test: `tests/test_briefing.py`

- [ ] **Step 1: Write briefing renderer test**

Create `tests/test_briefing.py`:

```python
from daily_tool_discovery.briefing import render_briefing
from daily_tool_discovery.models import Candidate, CandidateDecision


def test_render_briefing_groups_try_and_save_items():
    candidate = Candidate(
        id="github:Achilng/floral-notepaper",
        name="Achilng/floral-notepaper",
        url="https://github.com/Achilng/floral-notepaper",
        source="github",
        summary="Lightweight Markdown sticky notes",
        tags=["tauri", "markdown"],
        kind="open-source-small-tool",
        discovered_at="2026-06-05",
        metadata={"stars": 3500},
    )
    decision = CandidateDecision(
        candidate_id=candidate.id,
        action="try",
        score=80,
        reason="Matches local-first small-tool taste.",
        caveat="Check release package for your OS.",
    )

    markdown = render_briefing("2026-06-05", [(candidate, decision)])

    assert "# Daily Tool Discovery Briefing - 2026-06-05" in markdown
    assert "## Try Today" in markdown
    assert "### Achilng/floral-notepaper" in markdown
    assert "- 15-minute trial:" in markdown
    assert "## Save" in markdown
    assert "No saved items today." in markdown
```

- [ ] **Step 2: Run briefing test to verify it fails**

Run:

```bash
python -m pytest tests/test_briefing.py -q
```

Expected: FAIL with missing `daily_tool_discovery.briefing`.

- [ ] **Step 3: Implement briefing renderer**

Create `src/daily_tool_discovery/briefing.py`:

```python
from __future__ import annotations

from daily_tool_discovery.models import Candidate, CandidateDecision


def render_briefing(date: str, selected: list[tuple[Candidate, CandidateDecision]]) -> str:
    try_items = [(c, d) for c, d in selected if d.action == "try"]
    save_items = [(c, d) for c, d in selected if d.action == "save"]
    ignore_items = [(c, d) for c, d in selected if d.action == "ignore"]

    lines = [f"# Daily Tool Discovery Briefing - {date}", ""]
    lines.extend(_render_section("Try Today", try_items, empty="No try-worthy item today.", include_trial=True))
    lines.extend(_render_section("Save", save_items, empty="No saved items today.", include_trial=False))
    lines.extend(_render_section("Ignore", ignore_items, empty="No explicit ignores today.", include_trial=False))
    return "\n".join(lines).rstrip() + "\n"


def _render_section(
    title: str,
    items: list[tuple[Candidate, CandidateDecision]],
    empty: str,
    include_trial: bool,
) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.extend([empty, ""])
        return lines

    for candidate, decision in items:
        lines.extend(
            [
                f"### {candidate.name}",
                f"- Link: {candidate.url}",
                f"- Type: {candidate.kind}",
                f"- Score: {decision.score}",
                f"- Why it matters: {decision.reason}",
            ]
        )
        if include_trial:
            lines.append("- 15-minute trial: Open the project page, inspect install steps, and decide whether to schedule an installation separately.")
        if decision.caveat:
            lines.append(f"- Risk or caveat: {decision.caveat}")
        lines.append("")

    return lines
```

- [ ] **Step 4: Run briefing tests**

Run:

```bash
python -m pytest tests/test_briefing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/daily_tool_discovery/briefing.py tests/test_briefing.py
git commit -m "feat: render daily briefing markdown"
```

## Task 7: CLI Dry Run Pipeline

**Files:**
- Create: `src/daily_tool_discovery/cli.py`
- Create: `config/sources.example.toml`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write CLI dry-run test**

Create `tests/test_cli.py`:

```python
from pathlib import Path

from daily_tool_discovery.cli import run_dry_run


def test_dry_run_uses_manual_seeds_and_writes_artifacts(tmp_path):
    seeds_dir = tmp_path / "seeds"
    seeds_dir.mkdir()
    (seeds_dir / "manual.jsonl").write_text(
        '{"name":"floral-notepaper","url":"https://github.com/Achilng/floral-notepaper","summary":"Markdown sticky notes","tags":["tauri","markdown"],"kind":"open-source-small-tool"}\n',
        encoding="utf-8",
    )

    run_dry_run(root=tmp_path, date="2026-06-05")

    candidates = tmp_path / "candidates" / "2026-06-05.jsonl"
    briefing = tmp_path / "briefings" / "2026-06-05.md"

    assert candidates.exists()
    assert briefing.exists()
    assert "floral-notepaper" in briefing.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run CLI test to verify it fails**

Run:

```bash
python -m pytest tests/test_cli.py -q
```

Expected: FAIL with missing `daily_tool_discovery.cli`.

- [ ] **Step 3: Implement CLI**

Create `src/daily_tool_discovery/cli.py`:

```python
from __future__ import annotations

import argparse
from datetime import date as date_type
from pathlib import Path

from daily_tool_discovery.briefing import render_briefing
from daily_tool_discovery.jsonl_store import append_jsonl
from daily_tool_discovery.ranking import select_daily_candidates
from daily_tool_discovery.seeds import load_manual_seeds


def run_dry_run(root: Path, date: str | None = None) -> None:
    current_date = date or date_type.today().isoformat()
    seed_path = root / "seeds" / "manual.jsonl"
    candidates = load_manual_seeds(seed_path, discovered_at=current_date)

    candidate_path = root / "candidates" / f"{current_date}.jsonl"
    briefing_path = root / "briefings" / f"{current_date}.md"

    append_jsonl(candidate_path, [candidate.to_dict() for candidate in candidates])
    selected = select_daily_candidates(candidates)

    briefing_path.parent.mkdir(parents=True, exist_ok=True)
    briefing_path.write_text(render_briefing(current_date, selected), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily-tool-discovery")
    subcommands = parser.add_subparsers(dest="command", required=True)

    dry_run = subcommands.add_parser("dry-run", help="Run the local manual-seed briefing pipeline")
    dry_run.add_argument("--root", type=Path, default=Path.cwd())
    dry_run.add_argument("--date", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "dry-run":
        run_dry_run(root=args.root, date=args.date)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
```

Create `config/sources.example.toml`:

```toml
[[github_search]]
name = "agent-dev-mainline"
query = "agent mcp ai-coding CLI tool"
kind = "agent-dev-tool"
per_page = 10

[[github_search]]
name = "local-first-small-tools"
query = "tauri markdown local-first macos notes"
kind = "open-source-small-tool"
per_page = 10
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
python -m pytest tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

Run:

```bash
python -m pytest -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/daily_tool_discovery/cli.py tests/test_cli.py config/sources.example.toml
git commit -m "feat: add dry-run briefing cli"
```

## Task 8: Feedback Logging

**Files:**
- Create: `src/daily_tool_discovery/feedback.py`
- Modify: `src/daily_tool_discovery/cli.py`
- Test: `tests/test_feedback.py`

- [ ] **Step 1: Write feedback tests**

Create `tests/test_feedback.py`:

```python
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
```

- [ ] **Step 2: Run feedback tests to verify they fail**

Run:

```bash
python -m pytest tests/test_feedback.py -q
```

Expected: FAIL with missing `daily_tool_discovery.feedback`.

- [ ] **Step 3: Implement feedback model**

Create `src/daily_tool_discovery/feedback.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from daily_tool_discovery.jsonl_store import append_jsonl


FeedbackVerdict = Literal["tried", "saved", "ignored"]


@dataclass(frozen=True)
class FeedbackRecord:
    date: str
    candidate_id: str
    verdict: FeedbackVerdict
    value: str
    note: str = ""

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
```

- [ ] **Step 4: Add feedback CLI command**

Update `src/daily_tool_discovery/cli.py` to include these imports:

```python
from daily_tool_discovery.feedback import FeedbackRecord, append_feedback
```

Extend `build_parser()` after the `dry-run` parser:

```python
    feedback = subcommands.add_parser("feedback", help="Append lightweight feedback for a candidate")
    feedback.add_argument("--root", type=Path, default=Path.cwd())
    feedback.add_argument("--date", required=True)
    feedback.add_argument("--candidate-id", required=True)
    feedback.add_argument("--verdict", choices=["tried", "saved", "ignored"], required=True)
    feedback.add_argument("--value", required=True)
    feedback.add_argument("--note", default="")
```

Extend `main()` before the unknown-command error:

```python
    if args.command == "feedback":
        append_feedback(
            args.root / "feedback.jsonl",
            FeedbackRecord(
                date=args.date,
                candidate_id=args.candidate_id,
                verdict=args.verdict,
                value=args.value,
                note=args.note,
            ),
        )
        return 0
```

- [ ] **Step 5: Run feedback tests**

Run:

```bash
python -m pytest tests/test_feedback.py -q
```

Expected: PASS.

- [ ] **Step 6: Run CLI tests**

Run:

```bash
python -m pytest tests/test_cli.py tests/test_feedback.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/daily_tool_discovery/feedback.py src/daily_tool_discovery/cli.py tests/test_feedback.py
git commit -m "feat: add feedback logging"
```

## Task 9: Hermes Prompt Interface And Documentation

**Files:**
- Create: `prompts/hermes-review.md`
- Modify: `README.md`
- Test: `tests/test_docs.py`

- [ ] **Step 1: Write documentation smoke test**

Create `tests/test_docs.py`:

```python
from pathlib import Path


def test_readme_documents_dry_run_command():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "daily-tool-discovery dry-run" in readme
    assert "daily-tool-discovery feedback" in readme
    assert "seeds/manual.example.jsonl" in readme


def test_hermes_prompt_mentions_no_installation():
    prompt = Path("prompts/hermes-review.md").read_text(encoding="utf-8")

    assert "Do not install" in prompt
    assert "try, save, or ignore" in prompt
```

- [ ] **Step 2: Run docs tests to verify they fail**

Run:

```bash
python -m pytest tests/test_docs.py -q
```

Expected: FAIL because `README.md` and `prompts/hermes-review.md` do not yet contain the required content.

- [ ] **Step 3: Add Hermes review prompt**

Create `prompts/hermes-review.md`:

```md
# Hermes Tool Discovery Review Prompt

You are reviewing candidate tools for the Daily Tool Discovery briefing.

Prioritize:

- Agent/dev tooling for Codex, Claude Code, Hermes, MCP, skills, AI coding, terminal workflow, and developer automation.
- Open-source small tools for Tauri, Electron, Rust, TypeScript, macOS, Markdown, Obsidian, CLI, and local-first workflows.

Do not install tools, purchase subscriptions, mutate the user's environment, or execute setup commands.

For each selected candidate, classify it as try, save, or ignore.

Return at most three selected items. Prefer no "try" item over a weak forced recommendation.
```

- [ ] **Step 4: Update README**

Replace `README.md` with:

```md
# Daily Tool Discovery

Daily Tool Discovery is a server-side briefing workflow for finding useful tools without relying on social feeds.

The project focuses on:

- Agent/dev tooling: Codex, Claude Code, Hermes, MCP servers, skills, AI coding tools, terminal/dev workflow tools.
- Open-source small tools: Tauri, Electron, Rust, TypeScript, macOS, Markdown, Obsidian, CLI, and local-first utilities.

The intended v1 shape is a deterministic collector plus a Hermes review layer:

- Collect and normalize candidate tools.
- Deduplicate and filter candidates.
- Let Hermes score, explain, and select a short daily briefing.
- Save inspectable Markdown and JSONL artifacts.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Manual Seeds

Copy the example seed file before the first dry run:

```bash
mkdir -p seeds
cp seeds/manual.example.jsonl seeds/manual.jsonl
```

## Dry Run

```bash
daily-tool-discovery dry-run --root . --date 2026-06-05
```

Artifacts:

- `candidates/YYYY-MM-DD.jsonl`
- `briefings/YYYY-MM-DD.md`

## Feedback

```bash
daily-tool-discovery feedback \
  --root . \
  --date 2026-06-05 \
  --candidate-id github:Achilng/floral-notepaper \
  --verdict tried \
  --value useful \
  --note "Good local-first small-tool sample"
```

Feedback is appended to `feedback.jsonl`.

## Design

See [docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md](docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md).
```

- [ ] **Step 5: Run docs tests**

Run:

```bash
python -m pytest tests/test_docs.py -q
```

Expected: PASS.

- [ ] **Step 6: Run full verification**

Run:

```bash
python -m pytest -q
git diff --check
```

Expected: all tests PASS and `git diff --check` produces no output.

- [ ] **Step 7: Commit**

```bash
git add README.md prompts/hermes-review.md tests/test_docs.py
git commit -m "docs: document dry run and hermes review prompt"
```

## Task 10: Final MVP Smoke Run

**Files:**
- No new files expected.
- Runtime artifacts are ignored by `.gitignore`.

- [ ] **Step 1: Install package in editable mode**

Run:

```bash
python -m pip install -e ".[dev]"
```

Expected: package installs successfully.

- [ ] **Step 2: Prepare manual seeds**

Run:

```bash
mkdir -p seeds
cp seeds/manual.example.jsonl seeds/manual.jsonl
```

Expected: `seeds/manual.jsonl` exists and contains CodeIsland plus floral-notepaper examples.

- [ ] **Step 3: Run dry-run briefing**

Run:

```bash
daily-tool-discovery dry-run --root . --date 2026-06-05
```

Expected:

- `candidates/2026-06-05.jsonl` exists.
- `briefings/2026-06-05.md` exists.
- Briefing contains at most three selected items.

- [ ] **Step 4: Inspect generated briefing**

Run:

```bash
sed -n '1,180p' briefings/2026-06-05.md
```

Expected: Markdown includes `Daily Tool Discovery Briefing`, a `Try Today` section, and either CodeIsland or floral-notepaper.

- [ ] **Step 5: Run final tests**

Run:

```bash
python -m pytest -q
git status --short
```

Expected: tests PASS. `git status --short` may show ignored runtime files only if `--ignored` is used; normal status should be clean after commits.

## Spec Coverage Self-Review

- Tool discovery scope is covered by model kinds, seed examples, ranking tags, and config source examples.
- Deterministic collection is covered by manual seeds, GitHub client, JSONL artifacts, and dry-run CLI.
- Hermes review layer is covered by `prompts/hermes-review.md` and the decision interface. Direct Hermes CLI invocation remains outside MVP execution because the server invocation contract is still open.
- Storage is covered by JSONL candidate artifacts and Markdown briefing output.
- Daily briefing format is covered by `briefing.py` and renderer tests.
- Feedback loop is covered by `feedback.py`, `daily-tool-discovery feedback`, and `feedback.jsonl`.
- Public web search is not included in v1 execution; the MVP starts with API/feed-style and manual seed sources.
