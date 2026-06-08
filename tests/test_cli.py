import json
from pathlib import Path

from daily_tool_discovery import cli
from daily_tool_discovery.models import Candidate

PROFILE = """
[meta]
name = "t"
[[category]]
name = "agents"
weight = 2
signal_tags = ["mcp", "agent"]
  [[category.search]]
  name = "main"
  query = "topic:mcp"
  min_stars = 20
[[category]]
name = "frontend"
weight = 1
signal_tags = ["react", "vue"]
[trust]
min_stars = 20
[recommend]
cold_start_min_saves = 1
explore_slots = 1
"""


def _write_profile(root: Path):
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "profile.toml").write_text(PROFILE, encoding="utf-8")


class _StubGitHub:
    def __init__(self):
        self.users = {
            "alice": {"created_at": "2015-01-01T00:00:00Z", "public_repos": 50, "followers": 300},
            "carol": {"created_at": "2020-01-01T00:00:00Z", "public_repos": 12, "followers": 40},
            "frank": {"created_at": "2014-01-01T00:00:00Z", "public_repos": 80, "followers": 900},
        }

    def search_repositories(self, query, discovered_at, kind, per_page=10, min_stars=0):
        return [
            Candidate(id="github:alice/good", name="alice/good", url="https://github.com/alice/good",
                      source="github", summary="great mcp tool", tags=["mcp", "agent"], kind=kind,
                      discovered_at=discovered_at,
                      metadata={"category": kind, "stars": 800, "forks": 120, "open_issues": 6,
                                "created_at": "2023-01-01T00:00:00Z", "pushed_at": "2026-06-01T00:00:00Z",
                                "owner_login": "alice", "owner_type": "User", "archived": False, "is_fork": False}),
            Candidate(id="github:frank/offbeat", name="frank/offbeat", url="https://github.com/frank/offbeat",
                      source="github", summary="a database engine", tags=["database"], kind=kind,
                      discovered_at=discovered_at,
                      metadata={"category": kind, "stars": 500, "forks": 60, "open_issues": 3,
                                "created_at": "2022-01-01T00:00:00Z", "pushed_at": "2026-06-01T00:00:00Z",
                                "owner_login": "frank", "owner_type": "User", "archived": False, "is_fork": False}),
            Candidate(id="github:carol/tiny", name="carol/tiny", url="https://github.com/carol/tiny",
                      source="github", summary="small mcp helper", tags=["mcp"], kind=kind,
                      discovered_at=discovered_at,
                      metadata={"category": kind, "stars": 3, "forks": 0, "open_issues": 0,
                                "created_at": "2025-01-01T00:00:00Z", "pushed_at": "2026-05-01T00:00:00Z",
                                "owner_login": "carol", "owner_type": "User", "archived": False, "is_fork": False}),
            Candidate(id="github:BlueElephant42/x", name="BlueElephant42/x", url="https://github.com/BlueElephant42/x",
                      source="github", summary="", tags=["mcp", "agent"], kind=kind,
                      discovered_at=discovered_at,
                      metadata={"category": kind, "stars": 0, "forks": 0, "open_issues": 0,
                                "created_at": "2026-06-05T00:00:00Z", "pushed_at": "2026-06-05T00:00:00Z",
                                "owner_login": "BlueElephant42", "owner_type": "User", "archived": False, "is_fork": False}),
        ]

    def get_user(self, login):
        return self.users.get(login, {"created_at": "2026-06-01T00:00:00Z", "public_repos": 1, "followers": 0})


def _run(root, monkeypatch, date_str="2026-06-07"):
    monkeypatch.setattr(cli, "_make_github_client", lambda: _StubGitHub())
    cli.run_discover(root=root, date=date_str)


def test_discover_promotes_trusted_and_quarantines_malware(tmp_path, monkeypatch):
    _write_profile(tmp_path)
    _run(tmp_path, monkeypatch)
    briefing = (tmp_path / "briefings" / "2026-06-07.md").read_text(encoding="utf-8")
    assert "## Try Today" in briefing
    assert "alice/good" in briefing
    assert "BlueElephant42" not in briefing.split("## Recommended")[0]   # never a try
    assert "carol/tiny" in briefing.split("## Review yourself")[1].split("## 🎲 Explore")[0]


def test_briefing_filtered_line_names_repos_and_reasons(tmp_path, monkeypatch):
    _write_profile(tmp_path)
    _run(tmp_path, monkeypatch)
    briefing = (tmp_path / "briefings" / "2026-06-07.md").read_text(encoding="utf-8")
    line = next(l for l in briefing.splitlines() if l.startswith("Filtered"))
    # the rejected repo is named with its reason, not just counted
    assert "BlueElephant42/x" in line
    assert "no-community" in line


def test_inbox_has_trust_tier_and_relevance(tmp_path, monkeypatch):
    _write_profile(tmp_path)
    _run(tmp_path, monkeypatch)
    rows = [json.loads(l) for l in (tmp_path / "candidates" / "2026-06-07.jsonl").read_text().splitlines()]
    by_id = {r["id"]: r for r in rows}
    assert by_id["github:BlueElephant42/x"]["metadata"]["trust_tier"] == "reject"
    assert by_id["github:alice/good"]["metadata"]["trust_tier"] == "trusted"
    assert by_id["github:alice/good"]["metadata"]["relevance_points"] > 0
    assert by_id["github:frank/offbeat"]["metadata"]["taste_matched"] is False  # off-profile


def test_explore_pick_is_off_profile(tmp_path, monkeypatch):
    _write_profile(tmp_path)
    _run(tmp_path, monkeypatch)
    briefing = (tmp_path / "briefings" / "2026-06-07.md").read_text(encoding="utf-8")
    explore = briefing.split("## 🎲 Explore")[1]
    assert "frank/offbeat" in explore   # the trusted off-taste repo


def test_deny_removes_repo(tmp_path, monkeypatch):
    _write_profile(tmp_path)
    cli.run_deny(root=tmp_path, pattern="alice/good")
    _run(tmp_path, monkeypatch)
    briefing = (tmp_path / "briefings" / "2026-06-07.md").read_text(encoding="utf-8")
    assert "alice/good" not in briefing


def test_save_excludes_and_boosts(tmp_path, monkeypatch):
    _write_profile(tmp_path)
    _run(tmp_path, monkeypatch)  # seeds candidates/ for the index
    cli.run_save(root=tmp_path, candidate_id="github:alice/good", note="")
    _run(tmp_path, monkeypatch, date_str="2026-07-20")  # outside novelty window
    briefing = (tmp_path / "briefings" / "2026-07-20.md").read_text(encoding="utf-8")
    assert "alice/good" not in briefing   # saved -> not re-recommended


def test_dry_run_still_works(tmp_path):
    (tmp_path / "seeds").mkdir()
    (tmp_path / "seeds" / "manual.jsonl").write_text(
        json.dumps({"name": "Seed", "url": "https://github.com/me/seed", "kind": "agents", "tags": ["mcp"]}) + "\n",
        encoding="utf-8")
    cli.run_dry_run(root=tmp_path, date="2026-06-07")
    out = (tmp_path / "briefings" / "2026-06-07.md").read_text(encoding="utf-8")
    assert "# Daily Tool Discovery Briefing - 2026-06-07" in out


def test_feedback_and_save_cli(tmp_path):
    assert cli.main(["save", "--root", str(tmp_path), "--candidate-id", "github:a/b"]) == 0
    assert cli.main(["deny", "--root", str(tmp_path), "--pattern", "a/b"]) == 0
    assert (tmp_path / "feedback.jsonl").exists()
    assert "a/b" in (tmp_path / "denylist.txt").read_text(encoding="utf-8")
