from daily_tool_discovery.github_client import GitHubClient, candidate_from_github_payload


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


def test_payload_captures_trust_metadata():
    payload = {
        "full_name": "owner/repo",
        "html_url": "https://github.com/owner/repo",
        "description": "desc",
        "topics": ["cli"],
        "stargazers_count": 120,
        "forks_count": 30,
        "open_issues_count": 7,
        "created_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2026-06-01T00:00:00Z",
        "language": "Rust",
        "homepage": "",
        "archived": False,
        "fork": False,
        "owner": {"login": "owner", "type": "User"},
    }
    candidate = candidate_from_github_payload(payload, "2026-06-07", "agent-dev-tool", source="github")
    md = candidate.metadata
    assert md["stars"] == 120
    assert md["forks"] == 30
    assert md["open_issues"] == 7
    assert md["created_at"] == "2024-01-01T00:00:00Z"
    assert md["owner_login"] == "owner"
    assert md["owner_type"] == "User"
    assert md["archived"] is False
    assert md["is_fork"] is False


def test_payload_trust_metadata_defaults_when_missing():
    payload = {"full_name": "o/r", "html_url": "https://github.com/o/r"}
    candidate = candidate_from_github_payload(payload, "2026-06-07", "other", source="github")
    md = candidate.metadata
    assert md["forks"] == 0
    assert md["open_issues"] == 0
    assert md["created_at"] is None
    assert md["owner_login"] == ""
    assert md["owner_type"] == ""
    assert md["archived"] is False
    assert md["is_fork"] is False


class _FakeUserTransport:
    def __init__(self, payload):
        self.payload = payload
        self.url = None

    def get_json(self, url, headers):
        self.url = url
        return self.payload


def test_get_user_calls_users_endpoint():
    transport = _FakeUserTransport({"login": "alice", "followers": 9})
    client = GitHubClient(transport=transport)
    user = client.get_user("alice")
    assert transport.url == "https://api.github.com/users/alice"
    assert user["followers"] == 9


class _FakeSearchTransport:
    def __init__(self):
        self.url = None

    def get_json(self, url, headers):
        self.url = url
        return {"items": []}


def test_search_appends_stars_floor():
    transport = _FakeSearchTransport()
    client = GitHubClient(transport=transport)
    client.search_repositories("agent mcp cli", "2026-06-07", "agent-dev-tool", min_stars=20)
    assert "stars%3A%3E%3D20" in transport.url  # urlencoded "stars:>=20"


def test_search_does_not_double_append_when_query_has_stars():
    transport = _FakeSearchTransport()
    client = GitHubClient(transport=transport)
    client.search_repositories("agent stars:>=100", "2026-06-07", "agent-dev-tool", min_stars=20)
    assert "stars%3A%3E%3D100" in transport.url
    assert "stars%3A%3E%3D20" not in transport.url
