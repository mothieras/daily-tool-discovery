from pathlib import Path


def test_readme_documents_dry_run_command():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "daily-tool-discovery dry-run" in readme
    assert "daily-tool-discovery feedback" in readme
    assert "seeds/manual.example.jsonl" in readme


def test_hermes_prompt_mentions_no_installation():
    prompt = Path("prompts/hermes-review.md").read_text(encoding="utf-8")

    assert "Do not install" in prompt
    assert "try, save, or ignore" in prompt
