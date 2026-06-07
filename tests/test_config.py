from daily_tool_discovery.config import TrustConfig, load_config


def test_defaults():
    cfg = load_config(env={})
    assert cfg.min_stars == 20
    assert cfg.novelty_days == 30
    assert cfg.new_repo_days == 30
    assert cfg.stale_months == 12


def test_env_overrides():
    cfg = load_config(env={
        "DAILY_TOOL_DISCOVERY_MIN_STARS": "50",
        "DAILY_TOOL_DISCOVERY_NOVELTY_DAYS": "7",
        "DAILY_TOOL_DISCOVERY_NEW_REPO_DAYS": "14",
        "DAILY_TOOL_DISCOVERY_STALE_MONTHS": "6",
    })
    assert cfg == TrustConfig(min_stars=50, novelty_days=7, new_repo_days=14, stale_months=6)


def test_cli_overrides_win_over_env():
    cfg = load_config(env={"DAILY_TOOL_DISCOVERY_MIN_STARS": "50"}, min_stars=10, novelty_days=99)
    assert cfg.min_stars == 10
    assert cfg.novelty_days == 99


def test_invalid_env_falls_back_to_default():
    cfg = load_config(env={"DAILY_TOOL_DISCOVERY_MIN_STARS": "not-a-number"})
    assert cfg.min_stars == 20
