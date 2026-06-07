import json
from pathlib import Path

from daily_tool_discovery import cli
from daily_tool_discovery.models import Candidate


def _write_sources(root: Path):
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "sources.toml").write_text(
        '[[github_search]]\nname = "main"\nquery = "agent"\nkind = "agent-dev-tool"\nmin_stars = 20\n',
        encoding="utf-8",
    )


class _StubGitHub:
    """Returns one trusted repo, one low-star repo, one malware-shaped repo."""

    def __init__(self):
        # Established accounts: not suspicious. Any login not listed falls back to a
        # brand-new lonely account (suspicious), so list every legit finalist here.
        self.users = {
            "alice": {"created_at": "2015-01-01T00:00:00Z", "public_repos": 50, "followers": 300},
            "carol": {"created_at": "2020-01-01T00:00:00Z", "public_repos": 12, "followers": 40},
        }

    def search_repositories(self, query, discovered_at, kind, per_page=10, min_stars=0):
        return [
            Candidate(id="github:alice/good", name="alice/good", url="https://github.com/alice/good",
                      source="github", summary="great", tags=["agent", "mcp"], kind="agent-dev-tool",
                      discovered_at=discovered_at,
                      metadata={"stars": 800, "forks": 120, "open_issues": 6,
                                "created_at": "2023-01-01T00:00:00Z", "pushed_at": "2026-06-01T00:00:00Z",
                                "owner_login": "alice", "owner_type": "User", "archived": False, "is_fork": False}),
            Candidate(id="github:carol/tiny", name="carol/tiny", url="https://github.com/carol/tiny",
                      source="github", summary="small", tags=["cli"], kind="open-source-small-tool",
                      discovered_at=discovered_at,
                      metadata={"stars": 3, "forks": 0, "open_issues": 0,
                                "created_at": "2025-01-01T00:00:00Z", "pushed_at": "2026-05-01T00:00:00Z",
                                "owner_login": "carol", "owner_type": "User", "archived": False, "is_fork": False}),
            Candidate(id="github:BlueElephant42/x", name="BlueElephant42/x", url="https://github.com/BlueElephant42/x",
                      source="github", summary="", tags=["agent", "mcp", "cli"], kind="agent-dev-tool",
                      discovered_at=discovered_at,
                      metadata={"stars": 0, "forks": 0, "open_issues": 0,
                                "created_at": "2026-06-05T00:00:00Z", "pushed_at": "2026-06-05T00:00:00Z",
                                "owner_login": "BlueElephant42", "owner_type": "User", "archived": False, "is_fork": False}),
        ]

    def get_user(self, login):
        return self.users.get(login, {"created_at": "2026-06-01T00:00:00Z", "public_repos": 1, "followers": 0})


def _run(root, monkeypatch, date_str="2026-06-07"):
    monkeypatch.setattr(cli, "_make_github_client", lambda: _StubGitHub())
    cli.run_discover(root=root, date=date_str)


def test_discover_promotes_trusted_and_quarantines_malware(tmp_path, monkeypatch):
    _write_sources(tmp_path)
    _run(tmp_path, monkeypatch)
    briefing = (tmp_path / "briefings" / "2026-06-07.md").read_text(encoding="utf-8")
    assert "## Try Today" in briefing
    assert "alice/good" in briefing
    # malware-shaped repo must never be a try item
    try_section = briefing.split("## Save")[0]
    assert "BlueElephant42" not in try_section
    # low-star on-topic goes to review
    assert "carol/tiny" in briefing.split("## Review yourself")[1]


def test_full_pool_written_to_candidates_inbox(tmp_path, monkeypatch):
    _write_sources(tmp_path)
    _run(tmp_path, monkeypatch)
    rows = [json.loads(l) for l in (tmp_path / "candidates" / "2026-06-07.jsonl").read_text().splitlines()]
    ids = {r["id"] for r in rows}
    assert {"github:alice/good", "github:carol/tiny", "github:BlueElephant42/x"} <= ids
    # each candidate carries its trust tier
    tier_by_id = {r["id"]: r["metadata"].get("trust_tier") for r in rows}
    assert tier_by_id["github:BlueElephant42/x"] == "reject"
    assert tier_by_id["github:alice/good"] == "trusted"


def test_negative_feedback_suppresses_next_run(tmp_path, monkeypatch):
    _write_sources(tmp_path)
    _run(tmp_path, monkeypatch)
    cli.run_feedback(root=tmp_path, date="2026-06-07", candidate_id="github:alice/good",
                     verdict="tried", value="not useful", note="")
    _run(tmp_path, monkeypatch, date_str="2026-07-10")  # outside novelty window, but suppressed
    briefing = (tmp_path / "briefings" / "2026-07-10.md").read_text(encoding="utf-8")
    assert "alice/good" not in briefing


def test_novelty_prevents_same_day_repeat(tmp_path, monkeypatch):
    _write_sources(tmp_path)
    _run(tmp_path, monkeypatch, date_str="2026-06-07")
    _run(tmp_path, monkeypatch, date_str="2026-06-08")  # within 30-day window
    briefing = (tmp_path / "briefings" / "2026-06-08.md").read_text(encoding="utf-8")
    # alice/good already surfaced on 06-07 -> not re-surfaced as try/save
    assert "## Try Today" in briefing
    assert "alice/good" not in briefing.split("Filtered")[0].split("## Review yourself")[0]


def test_dry_run_produces_briefing(tmp_path):
    (tmp_path / "seeds").mkdir()
    (tmp_path / "seeds" / "manual.jsonl").write_text(
        json.dumps({"name": "Seed", "url": "https://github.com/me/seed",
                    "kind": "agent-dev-tool", "tags": ["agent"]}) + "\n",
        encoding="utf-8",
    )
    cli.run_dry_run(root=tmp_path, date="2026-06-07")
    out = (tmp_path / "briefings" / "2026-06-07.md").read_text(encoding="utf-8")
    assert "# Daily Tool Discovery Briefing - 2026-06-07" in out


def test_feedback_cli_appends_record(tmp_path):
    rc = cli.main([
        "feedback", "--root", str(tmp_path), "--date", "2026-06-07",
        "--candidate-id", "github:a/b", "--verdict", "tried", "--value", "useful",
    ])
    assert rc == 0
    rows = (tmp_path / "feedback.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1 and "github:a/b" in rows[0]
