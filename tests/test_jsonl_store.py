import pytest

from daily_tool_discovery.jsonl_store import append_jsonl, read_jsonl


def test_append_and_read_jsonl(tmp_path):
    path = tmp_path / "items.jsonl"

    append_jsonl(path, [{"name": "CodeIsland"}, {"name": "floral-notepaper"}])

    assert read_jsonl(path) == [
        {"name": "CodeIsland"},
        {"name": "floral-notepaper"},
    ]


def test_read_missing_jsonl_returns_empty_list(tmp_path):
    assert read_jsonl(tmp_path / "missing.jsonl") == []


def test_read_jsonl_ignores_blank_lines(tmp_path):
    path = tmp_path / "items.jsonl"
    path.write_text(
        '\n{"name": "CodeIsland"}\n\n{"name": "floral-notepaper"}\n\n',
        encoding="utf-8",
    )

    assert read_jsonl(path) == [
        {"name": "CodeIsland"},
        {"name": "floral-notepaper"},
    ]


def test_read_invalid_jsonl_includes_file_and_line(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text('{"name":\n', encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        read_jsonl(path)

    message = str(exc_info.value)
    assert str(path) in message
    assert ":1:" in message
    assert "Invalid JSONL" in message


def test_read_non_object_jsonl_row_includes_file_and_line(tmp_path):
    path = tmp_path / "items.jsonl"
    path.write_text('[]\n', encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        read_jsonl(path)

    message = str(exc_info.value)
    assert str(path) in message
    assert ":1:" in message
    assert "object" in message
