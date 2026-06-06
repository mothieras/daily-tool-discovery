from pathlib import Path

from daily_tool_discovery.cli import build_parser


def test_readme_documents_dry_run_command():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "python -m pip install -e \".[dev]\"" in readme
    assert "daily-tool-discovery dry-run" in readme
    assert "daily-tool-discovery feedback" in readme
    assert "seeds/manual.example.jsonl" in readme
    assert "candidates/YYYY-MM-DD.jsonl" in readme
    assert "briefings/YYYY-MM-DD.md" in readme
    assert (
        "docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md"
        in readme
    )


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
    assert "feedback" in help_text
