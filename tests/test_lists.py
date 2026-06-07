from daily_tool_discovery.lists import load_denylist, is_denied, append_denylist


def test_glob_and_exact_match():
    patterns = ("bad/*", "owner/repo")
    assert is_denied("github:bad/anything", patterns) is True
    assert is_denied("github:owner/repo", patterns) is True
    assert is_denied("github:owner/other", patterns) is False
    assert is_denied("github:good/repo", patterns) is False


def test_load_denylist_merges_file_and_static(tmp_path):
    f = tmp_path / "denylist.txt"
    f.write_text("# comment\nfromfile/*\n\n", encoding="utf-8")
    merged = load_denylist(f, ("static/*",))
    assert set(merged) == {"fromfile/*", "static/*"}


def test_load_denylist_missing_file(tmp_path):
    assert load_denylist(tmp_path / "none.txt", ("static/*",)) == ("static/*",)


def test_append_denylist_is_idempotent(tmp_path):
    f = tmp_path / "denylist.txt"
    append_denylist(f, "owner/repo")
    append_denylist(f, "owner/repo")
    lines = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    assert lines == ["owner/repo"]
