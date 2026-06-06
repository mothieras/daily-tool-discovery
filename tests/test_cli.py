import pytest

from daily_tool_discovery.cli import run_dry_run


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
