from datetime import date

from daily_tool_discovery.config import TrustConfig
from daily_tool_discovery.models import Candidate
from daily_tool_discovery.trust import (
    assess_trust,
    annotate_trust,
    is_auto_generated_login,
    publisher_is_suspicious,
)

TODAY = date(2026, 6, 7)
CFG = TrustConfig()


def _candidate(**md):
    return Candidate(
        id="github:o/r", name="o/r", url="https://github.com/o/r",
        source="github_search:x", summary="s", tags=["cli"], kind="agent-dev-tool",
        discovered_at="2026-06-07", metadata=md,
    )


def test_auto_generated_login_matches_random_word_word_digits():
    assert is_auto_generated_login("BlueElephant42") is True
    assert is_auto_generated_login("SilverMountain7788") is True


def test_auto_generated_login_false_positives_guarded():
    assert is_auto_generated_login("John2024") is False   # single word + digits
    assert is_auto_generated_login("torvalds") is False
    assert is_auto_generated_login("facebook") is False
    assert is_auto_generated_login("BlueElephant") is False  # no digits


def test_reject_requires_full_malware_fingerprint():
    c = _candidate(
        stars=0, forks=0, created_at="2026-06-05T00:00:00Z",
        pushed_at="2026-06-05T00:00:00Z", owner_login="BlueElephant42",
    )
    assert assess_trust(c, TODAY, CFG).tier == "reject"


def test_single_signal_does_not_reject():
    # auto-gen name but has community and is old -> not reject
    c = _candidate(
        stars=300, forks=40, created_at="2023-01-01T00:00:00Z",
        pushed_at="2026-06-01T00:00:00Z", owner_login="BlueElephant42",
    )
    assert assess_trust(c, TODAY, CFG).tier == "trusted"


def test_trusted_requires_stars_floor_not_archived_and_active():
    c = _candidate(stars=25, forks=5, created_at="2024-01-01T00:00:00Z",
                   pushed_at="2026-06-01T00:00:00Z", owner_login="alice")  # 6 days -> fresh
    assert assess_trust(c, TODAY, CFG).tier == "trusted"


def test_small_repo_stale_beyond_window_is_review():
    # 100 stars < established_stars(500): 90 days > active_days(62) reads as abandoned -> review
    c = _candidate(stars=100, forks=10, created_at="2024-01-01T00:00:00Z",
                   pushed_at="2026-03-09T00:00:00Z", owner_login="alice")  # 90 days
    assessment = assess_trust(c, TODAY, CFG)
    assert assessment.tier == "review"
    assert "stale" in assessment.risk_flags


def test_established_repo_gets_relaxed_freshness_window():
    # same 90-day staleness, but 800 stars >= established_stars(500) -> within 150d -> trusted
    c = _candidate(stars=800, forks=100, created_at="2022-01-01T00:00:00Z",
                   pushed_at="2026-03-09T00:00:00Z", owner_login="alice")  # 90 days
    assessment = assess_trust(c, TODAY, CFG)
    assert assessment.tier == "trusted"
    assert "stale" not in assessment.risk_flags


def test_established_repo_beyond_relaxed_window_is_review():
    c = _candidate(stars=800, forks=100, created_at="2022-01-01T00:00:00Z",
                   pushed_at="2026-01-01T00:00:00Z", owner_login="alice")  # 158 days > 150
    assert assess_trust(c, TODAY, CFG).tier == "review"


def test_low_star_on_topic_is_review_not_reject():
    c = _candidate(stars=3, forks=1, created_at="2025-01-01T00:00:00Z",
                   pushed_at="2026-05-01T00:00:00Z", owner_login="alice")
    assert assess_trust(c, TODAY, CFG).tier == "review"


def test_archived_or_stale_popular_is_review():
    archived = _candidate(stars=900, forks=100, created_at="2019-01-01T00:00:00Z",
                          pushed_at="2026-05-01T00:00:00Z", owner_login="alice", archived=True)
    assert assess_trust(archived, TODAY, CFG).tier == "review"
    stale = _candidate(stars=900, forks=100, created_at="2017-01-01T00:00:00Z",
                       pushed_at="2021-01-01T00:00:00Z", owner_login="alice")
    assert assess_trust(stale, TODAY, CFG).tier == "review"


def test_missing_pushed_at_cannot_be_trusted():
    c = _candidate(stars=900, forks=100, created_at="2020-01-01T00:00:00Z", owner_login="alice")
    assert assess_trust(c, TODAY, CFG).tier == "review"


def test_annotate_trust_writes_tier_and_flags():
    c = _candidate(stars=0, forks=0, created_at="2026-06-05T00:00:00Z",
                   pushed_at="2026-06-05T00:00:00Z", owner_login="BlueElephant42")
    annotated = annotate_trust(c, assess_trust(c, TODAY, CFG))
    assert annotated.metadata["trust_tier"] == "reject"
    assert "auto-generated-username" in annotated.metadata["risk_flags"]


def test_publisher_suspicious_brand_new_lonely_account():
    user = {"created_at": "2026-06-01T00:00:00Z", "public_repos": 1, "followers": 0}
    assert publisher_is_suspicious(user, TODAY, CFG) is True


def test_publisher_not_suspicious_established_account():
    user = {"created_at": "2015-01-01T00:00:00Z", "public_repos": 40, "followers": 200}
    assert publisher_is_suspicious(user, TODAY, CFG) is False


def test_publisher_not_suspicious_when_has_followers():
    user = {"created_at": "2026-06-01T00:00:00Z", "public_repos": 1, "followers": 5}
    assert publisher_is_suspicious(user, TODAY, CFG) is False
