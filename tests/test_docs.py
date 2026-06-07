from pathlib import Path

from daily_tool_discovery.cli import build_parser


def test_readme_documents_dry_run_command():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "python -m pip install -e \".[dev]\"" in readme
    assert "daily-tool-discovery discover" in readme
    assert "daily-tool-discovery dry-run" in readme
    assert "daily-tool-discovery feedback" in readme
    assert "config/sources.example.toml" in readme
    assert "seeds/manual.example.jsonl" in readme
    assert "candidates/YYYY-MM-DD.jsonl" in readme
    assert "briefings/YYYY-MM-DD.md" in readme
    assert (
        "docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md"
        in readme
    )


def test_readme_documents_hermes_skill_cron_modes():
    readme = Path("README.md").read_text(encoding="utf-8").lower()

    assert "hermes integration is available" in readme
    assert "daily-tool-discovery` hermes skill" in readme
    assert "optional hermes cron" in readme
    assert "--no-agent" in readme
    assert "--skill daily-tool-discovery" in readme
    assert "no llm call" in readme


def test_hermes_prompt_scopes_review_to_provided_artifacts():
    prompt = Path("prompts/hermes-review.md").read_text(encoding="utf-8")
    prompt_lower = prompt.lower()

    assert "Do not install" in prompt
    assert "provided candidate artifacts" in prompt_lower
    assert "do not autonomously discover" in prompt_lower
    assert "fetch" in prompt_lower
    assert "set up" in prompt_lower or "setup" in prompt_lower
    assert "mutate" in prompt_lower
    assert "environment" in prompt_lower
    assert "briefing/feedback flow" in prompt_lower
    assert "try, save, or ignore" in prompt
    assert 'prefer no "try" item' in prompt_lower
    assert "weak forced recommendation" in prompt_lower
    assert "at most three" in prompt_lower or "max three" in prompt_lower


def test_cli_help_documents_dry_run_and_feedback_commands():
    help_text = build_parser().format_help()

    assert "dry-run" in help_text
    assert "discover" in help_text
    assert "feedback" in help_text


def test_skill_states_trust_floor():
    text = Path("hermes-skills/daily-tool-discovery/SKILL.md").read_text(encoding="utf-8")
    assert "20" in text  # the stars floor
    assert "Review yourself" in text
    assert "do not run blindly" in text.lower() or "audit" in text.lower()


def test_readme_documents_review_bucket():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "Review yourself" in text
