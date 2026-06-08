from datetime import date

from daily_tool_discovery.history import record_surfaced, load_recent_surfaced_ids
from daily_tool_discovery.models import Candidate, CandidateDecision


def _pair(cid, action="recommend"):
    c = Candidate(id=cid, name=cid, url="u", source="s", summary="", tags=[],
                  kind="other", discovered_at="2026-06-07")
    d = CandidateDecision(candidate_id=cid, action=action, score=1, reason="r")
    return c, d


def test_record_and_load_within_window(tmp_path):
    path = tmp_path / "history.jsonl"
    record_surfaced(path, "2026-06-07", [_pair("github:a/b"), _pair("github:c/d", "review")])
    ids = load_recent_surfaced_ids(path, date(2026, 6, 7), days=30)
    assert ids == {"github:a/b", "github:c/d"}


def test_old_entries_fall_out_of_window(tmp_path):
    path = tmp_path / "history.jsonl"
    record_surfaced(path, "2026-04-01", [_pair("github:old/one")])
    record_surfaced(path, "2026-06-07", [_pair("github:new/one")])
    ids = load_recent_surfaced_ids(path, date(2026, 6, 7), days=30)
    assert ids == {"github:new/one"}


def test_record_is_idempotent_per_date(tmp_path):
    path = tmp_path / "history.jsonl"
    record_surfaced(path, "2026-06-07", [_pair("github:a/b")])
    record_surfaced(path, "2026-06-07", [_pair("github:a/b"), _pair("github:e/f")])
    rows = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 2  # only the second write for that date is kept
    ids = load_recent_surfaced_ids(path, date(2026, 6, 7), days=30)
    assert ids == {"github:a/b", "github:e/f"}


def test_load_missing_file_returns_empty(tmp_path):
    assert load_recent_surfaced_ids(tmp_path / "nope.jsonl", date(2026, 6, 7), days=30) == set()
