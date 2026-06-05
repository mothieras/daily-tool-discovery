import pytest

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


def test_load_manual_seeds_missing_required_field_includes_file_line_and_field(tmp_path):
    path = tmp_path / "manual.jsonl"
    path.write_text(
        '{"name":"CodeIsland","summary":"Agent status panel"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_manual_seeds(path, discovered_at="2026-06-05")

    message = str(exc_info.value)
    assert str(path) in message
    assert ":1:" in message
    assert "url" in message


def test_load_manual_seeds_rejects_string_tags_with_file_line_context(tmp_path):
    path = tmp_path / "manual.jsonl"
    path.write_text(
        '{"name":"CodeIsland","url":"https://example.com/codeisland","tags":"abc"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_manual_seeds(path, discovered_at="2026-06-05")

    message = str(exc_info.value)
    assert str(path) in message
    assert ":1:" in message
    assert "tags" in message


def test_load_manual_seeds_invalid_kind_includes_file_line_context(tmp_path):
    path = tmp_path / "manual.jsonl"
    path.write_text(
        '{"name":"CodeIsland","url":"https://example.com/codeisland","kind":"invalid"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_manual_seeds(path, discovered_at="2026-06-05")

    message = str(exc_info.value)
    assert str(path) in message
    assert ":1:" in message
    assert "kind" in message
