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
