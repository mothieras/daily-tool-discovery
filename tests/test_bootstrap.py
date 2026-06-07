from __future__ import annotations

from pathlib import Path

from daily_tool_discovery.bootstrap import default_data_root, ensure_data_root


def test_default_data_root_honors_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_TOOL_DISCOVERY_HOME", str(tmp_path / "custom"))
    assert default_data_root() == tmp_path / "custom"


def test_default_data_root_falls_back_to_home(monkeypatch, tmp_path):
    monkeypatch.delenv("DAILY_TOOL_DISCOVERY_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "fakehome"))
    assert default_data_root() == tmp_path / "fakehome" / ".daily-tool-discovery"


def _make_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "templates").mkdir(parents=True)
    (bundle / "templates" / "profile.example.toml").write_text(
        "[meta]\nname = \"example\"\n", encoding="utf-8"
    )
    (bundle / "templates" / "manual.example.jsonl").write_text(
        "{\"name\":\"seed\"}\n", encoding="utf-8"
    )
    return bundle


def test_ensure_data_root_copies_examples_on_first_run(tmp_path):
    bundle = _make_bundle(tmp_path)
    data_root = tmp_path / "data"

    ensure_data_root(data_root, bundle)

    prof = data_root / "config" / "profile.toml"
    seed = data_root / "seeds" / "manual.jsonl"
    assert prof.exists()
    assert seed.exists()
    assert prof.read_text(encoding="utf-8") == "[meta]\nname = \"example\"\n"
    assert seed.read_text(encoding="utf-8") == "{\"name\":\"seed\"}\n"


def test_ensure_data_root_is_idempotent_and_preserves_edits(tmp_path):
    bundle = _make_bundle(tmp_path)
    data_root = tmp_path / "data"

    ensure_data_root(data_root, bundle)

    prof = data_root / "config" / "profile.toml"
    prof.write_text("[meta]\nname = \"edited\"\n", encoding="utf-8")

    ensure_data_root(data_root, bundle)

    assert prof.read_text(encoding="utf-8") == "[meta]\nname = \"edited\"\n"
