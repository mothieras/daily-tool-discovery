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
