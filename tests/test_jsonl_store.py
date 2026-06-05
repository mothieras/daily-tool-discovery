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
