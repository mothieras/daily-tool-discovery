import pytest

from daily_tool_discovery.cli import main, run_discover, run_dry_run
from daily_tool_discovery.models import Candidate
from daily_tool_discovery.jsonl_store import read_jsonl


def write_manual_seed(root):
    seeds_dir = root / "seeds"
    seeds_dir.mkdir()
    (seeds_dir / "manual.jsonl").write_text(
        '{"name":"floral-notepaper","url":"https://github.com/Achilng/floral-notepaper","summary":"Markdown sticky notes","tags":["tauri","markdown"],"kind":"open-source-small-tool"}\n',
        encoding="utf-8",
    )


def test_dry_run_uses_manual_seeds_and_writes_artifacts(tmp_path):
    write_manual_seed(tmp_path)

    run_dry_run(root=tmp_path, date="2026-06-05")

    candidates = tmp_path / "candidates" / "2026-06-05.jsonl"
    briefing = tmp_path / "briefings" / "2026-06-05.md"

    assert candidates.exists()
    assert briefing.exists()
    assert "floral-notepaper" in briefing.read_text(encoding="utf-8")


def test_dry_run_overwrites_daily_candidates_on_rerun(tmp_path):
    write_manual_seed(tmp_path)

    run_dry_run(root=tmp_path, date="2026-06-05")
    run_dry_run(root=tmp_path, date="2026-06-05")

    candidates = tmp_path / "candidates" / "2026-06-05.jsonl"

    assert len(candidates.read_text(encoding="utf-8").splitlines()) == 1


def test_dry_run_rejects_path_like_date_without_writing_artifacts(tmp_path):
    write_manual_seed(tmp_path)

    with pytest.raises(ValueError, match="Invalid dry-run date"):
        run_dry_run(root=tmp_path, date="../../escape")

    assert not (tmp_path / "candidates").exists()
    assert not (tmp_path / "briefings").exists()


def test_dry_run_requires_manual_seed_file_before_writing_artifacts(tmp_path):
    seeds_dir = tmp_path / "seeds"
    seeds_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="manual seed file not found"):
        run_dry_run(root=tmp_path, date="2026-06-05")

    assert not (tmp_path / "candidates").exists()
    assert not (tmp_path / "briefings").exists()


def test_discover_writes_candidates_and_briefing(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "sources.example.toml").write_text("[[sources]]\nname='fake'\nurl='https://example.com'\n", encoding="utf-8")
    candidate = Candidate(
        id="github:foo/bar",
        name="foo/bar",
        url="https://github.com/foo/bar",
        source="curated:fake",
        summary="Agent workflow tool",
        tags=["agent"],
        kind="agent-dev-tool",
        discovered_at="2026-06-06",
        metadata={"stars": 10},
    )
    monkeypatch.setattr("daily_tool_discovery.cli.load_curated_sources", lambda path: [])
    monkeypatch.setattr(
        "daily_tool_discovery.cli.discover_curated_candidates",
        lambda sources, discovered_at, limit: [candidate],
    )
    monkeypatch.setattr("daily_tool_discovery.cli.load_github_search_sources", lambda path: [])
    monkeypatch.setattr(
        "daily_tool_discovery.cli.discover_github_search_candidates",
        lambda searches, discovered_at, limit: [],
    )

    run_discover(root=tmp_path, date="2026-06-06")

    assert read_jsonl(tmp_path / "candidates" / "2026-06-06.jsonl")[0]["id"] == "github:foo/bar"
    assert "foo/bar" in (tmp_path / "briefings" / "2026-06-06.md").read_text(encoding="utf-8")


def test_feedback_command_writes_feedback_jsonl(tmp_path):
    result = main(
        [
            "feedback",
            "--root",
            str(tmp_path),
            "--date",
            "2026-06-05",
            "--candidate-id",
            "github:Achilng/floral-notepaper",
            "--verdict",
            "tried",
            "--value",
            "useful",
            "--note",
            "Worth keeping.",
        ]
    )

    assert result == 0
    assert read_jsonl(tmp_path / "feedback.jsonl") == [
        {
            "date": "2026-06-05",
            "candidate_id": "github:Achilng/floral-notepaper",
            "verdict": "tried",
            "value": "useful",
            "note": "Worth keeping.",
        }
    ]


def test_feedback_command_rejects_path_like_date_without_writing_feedback(tmp_path):
    with pytest.raises(SystemExit):
        main(
            [
                "feedback",
                "--root",
                str(tmp_path),
                "--date",
                "../../escape",
                "--candidate-id",
                "github:Achilng/floral-notepaper",
                "--verdict",
                "ignored",
                "--value",
                "not-useful",
            ]
        )

    assert not (tmp_path / "feedback.jsonl").exists()
