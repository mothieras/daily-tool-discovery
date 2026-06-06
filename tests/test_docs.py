from pathlib import Path

from daily_tool_discovery.cli import build_parser


def test_readme_documents_dry_run_command():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "daily-tool-discovery dry-run" in readme
    assert "daily-tool-discovery feedback" in readme
    assert "seeds/manual.example.jsonl" in readme


def test_readme_documents_hermes_review_not_wired():
    readme = Path("README.md").read_text(encoding="utf-8").lower()

    assert "hermes invocation is not wired" in readme
    assert "prompts/hermes-review.md" in readme
    assert "review prompt/interface artifact" in readme


def test_hermes_prompt_scopes_review_to_provided_artifacts():
    prompt = Path("prompts/hermes-review.md").read_text(encoding="utf-8")
    prompt_lower = prompt.lower()

    assert "Do not install" in prompt
    assert "provided candidate artifacts" in prompt_lower
    assert "do not autonomously discover" in prompt_lower
    assert "briefing/feedback flow" in prompt_lower
    assert "try, save, or ignore" in prompt


def test_cli_help_documents_dry_run_and_feedback_commands():
    help_text = build_parser().format_help()

    assert "dry-run" in help_text
    assert "feedback" in help_text
