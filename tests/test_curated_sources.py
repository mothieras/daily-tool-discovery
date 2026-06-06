from daily_tool_discovery.curated_sources import (
    CuratedSource,
    discover_curated_candidates,
    extract_github_repos,
)
from daily_tool_discovery.models import Candidate


class FakeTextTransport:
    def __init__(self, text):
        self.text = text

    def get_text(self, url):
        return self.text


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


def test_extract_github_repos_deduplicates_markdown_links():
    repos = extract_github_repos(
        "- [A](https://github.com/foo/bar)\n"
        "- https://github.com/foo/bar#readme\n"
        "- https://github.com/Org/tool.git\n"
        "- https://github.com/punkpeye/awesome-mcp-clients\n"
    )

    assert repos == ["foo/bar", "Org/tool"]


def test_discover_curated_candidates_uses_github_metadata():
    candidates = discover_curated_candidates(
        [CuratedSource(name="awesome", url="https://example.com/readme.md", kind="agent-dev-tool")],
        discovered_at="2026-06-06",
        text_transport=FakeTextTransport("https://github.com/foo/bar"),
        github_client=FakeGitHubClient(),
    )

    assert candidates[0].id == "github:foo/bar"
    assert candidates[0].source == "curated:awesome"
    assert candidates[0].metadata["stars"] == 100


def test_discover_curated_candidates_falls_back_when_metadata_fails():
    candidates = discover_curated_candidates(
        [CuratedSource(name="awesome", url="https://example.com/readme.md", kind="agent-dev-tool")],
        discovered_at="2026-06-06",
        text_transport=FakeTextTransport("https://github.com/foo/bar"),
        github_client=FakeGitHubClient(fail=True),
    )

    assert candidates[0].id == "github:foo/bar"
    assert candidates[0].metadata["metadata_error"] is True
