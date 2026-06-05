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
