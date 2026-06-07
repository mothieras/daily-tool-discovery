from urllib.error import HTTPError

from daily_tool_discovery.curated_sources import (
    CuratedSource,
    curated_source_from_row,
    discover_curated_candidates,
    extract_github_repos,
    github_search_from_row,
)
from daily_tool_discovery.models import Candidate


class FakeTextTransport:
    def __init__(self, text):
        self.text = text

    def get_text(self, url):
        return self.text


class FakeTextTransportByUrl:
    def __init__(self, texts):
        self.texts = texts

    def get_text(self, url):
        return self.texts[url]


class FakeGitHubClient:
    def __init__(self, fail=False):
        self.fail = fail

    def get_repository(self, full_name, discovered_at, kind, source):
        if self.fail:
            raise RuntimeError("metadata unavailable")
        return Candidate(
            id=f"github:{full_name}",
            name=full_name,
            url=f"https://github.com/{full_name}",
            source=source,
            summary="Useful tool",
            tags=["mcp"],
            kind=kind,
            discovered_at=discovered_at,
            metadata={"stars": 100},
        )


class FakeHttpErrorGitHubClient:
    def get_repository(self, full_name, discovered_at, kind, source):
        raise HTTPError("https://api.github.com/repos/foo/bar", 403, "rate limit", {}, None)


def test_extract_github_repos_deduplicates_markdown_links():
    repos = extract_github_repos(
        "- [A](https://github.com/foo/bar)\n"
        "- https://github.com/foo/bar#readme\n"
        "- https://github.com/Org/tool.git\n"
        "- https://github.com/punkpeye/awesome-mcp-clients\n"
    )

    assert repos == ["foo/bar", "Org/tool"]


def test_curated_source_from_row_injects_category():
    s = curated_source_from_row({"name": "x", "url": "https://e/r.md"}, category="cat-a")
    assert s.name == "x" and s.url == "https://e/r.md" and s.category == "cat-a"


def test_github_search_from_row_defaults_and_category():
    s = github_search_from_row({"name": "q", "query": "topic:mcp"}, category="cat-a")
    assert s.category == "cat-a" and s.per_page == 10 and s.min_stars == 20


def test_github_search_from_row_parses_min_stars():
    s = github_search_from_row(
        {"name": "x", "query": "agent", "min_stars": 50}, category="cat-a"
    )
    assert s.min_stars == 50


def test_curated_source_from_row_missing_field_raises():
    import pytest
    with pytest.raises(ValueError):
        curated_source_from_row({"name": "x"}, category="cat-a")  # no url


def test_discover_curated_candidates_uses_github_metadata():
    candidates = discover_curated_candidates(
        [CuratedSource(name="awesome", url="https://example.com/readme.md", category="agent-dev-tool")],
        discovered_at="2026-06-06",
        text_transport=FakeTextTransport("https://github.com/foo/bar"),
        github_client=FakeGitHubClient(),
    )

    assert candidates[0].id == "github:foo/bar"
    assert candidates[0].source == "curated:awesome"
    assert candidates[0].metadata["stars"] == 100


def test_discover_curated_candidates_falls_back_when_metadata_fails():
    candidates = discover_curated_candidates(
        [CuratedSource(name="awesome", url="https://example.com/readme.md", category="agent-dev-tool")],
        discovered_at="2026-06-06",
        text_transport=FakeTextTransport("https://github.com/foo/bar"),
        github_client=FakeGitHubClient(fail=True),
    )

    assert candidates[0].id == "github:foo/bar"
    assert candidates[0].metadata["metadata_error"] is True
    assert candidates[0].metadata["metadata_error_type"] == "RuntimeError"


def test_discover_curated_candidates_records_http_status_on_metadata_failure():
    candidates = discover_curated_candidates(
        [CuratedSource(name="awesome", url="https://example.com/readme.md", category="agent-dev-tool")],
        discovered_at="2026-06-06",
        text_transport=FakeTextTransport("https://github.com/foo/bar"),
        github_client=FakeHttpErrorGitHubClient(),
    )

    assert candidates[0].metadata["metadata_error_status"] == 403


def test_discover_curated_candidates_caps_each_source():
    candidates = discover_curated_candidates(
        [
            CuratedSource(name="first", url="https://example.com/first.md", category="agent-dev-tool"),
            CuratedSource(name="second", url="https://example.com/second.md", category="agent-dev-tool"),
        ],
        discovered_at="2026-06-06",
        limit=4,
        text_transport=FakeTextTransportByUrl(
            {
                "https://example.com/first.md": "\n".join(
                    [
                        "https://github.com/one/a",
                        "https://github.com/one/b",
                        "https://github.com/one/c",
                        "https://github.com/one/d",
                    ]
                ),
                "https://example.com/second.md": "\n".join(
                    [
                        "https://github.com/two/a",
                        "https://github.com/two/b",
                        "https://github.com/two/c",
                        "https://github.com/two/d",
                    ]
                ),
            }
        ),
        github_client=FakeGitHubClient(fail=True),
    )

    assert [candidate.source for candidate in candidates] == [
        "curated:first",
        "curated:first",
        "curated:second",
        "curated:second",
    ]
