# Daily Tool Discovery

Daily Tool Discovery is a server-side briefing workflow for finding useful tools without relying on social feeds.

The project focuses on:

- Agent/dev tooling: Codex, Claude Code, Hermes, MCP servers, skills, AI coding tools, terminal/dev workflow tools.
- Open-source small tools: Tauri, Electron, Rust, TypeScript, macOS, Markdown, Obsidian, CLI, and local-first utilities.

The implemented v1 shape is a local deterministic briefing pipeline:

- Collect and normalize candidate tools.
- Deduplicate and filter candidates.
- Rank and select candidates locally with deterministic rules.
- Save inspectable Markdown and JSONL artifacts.

Hermes invocation is not wired yet. `prompts/hermes-review.md` is a review prompt/interface artifact for a later integration, not something the current CLI executes. Today, `discover` can read curated source lists plus GitHub search config and write the candidate and briefing artifacts below.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Fast Server Install

This repository is private. On a server with Hermes and GitHub CLI already logged in:

```bash
mkdir -p ~/apps
gh repo clone mothieras/daily-tool-discovery ~/apps/daily-tool-discovery
cd ~/apps/daily-tool-discovery
bash scripts/install-hermes-server.sh --cron --deliver local
```

This installs the package, writes `~/.hermes/scripts/daily-tool-discovery.sh`, installs the `daily-tool-discovery` Hermes skill, runs one smoke discovery, and registers a no-agent Hermes cron job.

Use the agent-backed cron path if you want Hermes to review the generated briefing with the installed skill:

```bash
bash scripts/install-hermes-server.sh --agent-cron --deliver local
```

`--cron` is cheaper because it skips the LLM and delivers the generated briefing directly. `--agent-cron` spends Hermes model calls but lets Hermes apply the skill policy before delivering the result.

Useful checks:

```bash
~/.hermes/scripts/daily-tool-discovery.sh
hermes cron list
```

Optional: export `GITHUB_TOKEN` before running the script if the server hits GitHub API rate limits.

Installed Hermes files:

- `~/.hermes/scripts/daily-tool-discovery.sh`
- `~/.hermes/skills/software-development/daily-tool-discovery/SKILL.md`

## Discover

Run the live discovery pipeline:

```bash
daily-tool-discovery discover --root . --date 2026-06-06
```

By default this reads `config/sources.toml` if it exists, otherwise `config/sources.example.toml`.

Artifacts:

- `candidates/YYYY-MM-DD.jsonl`
- `briefings/YYYY-MM-DD.md`

## Manual Seeds

Manual seeds are still useful for friend recommendations or projects you already know about:

```bash
mkdir -p seeds
cp seeds/manual.example.jsonl seeds/manual.jsonl
daily-tool-discovery dry-run --root . --date 2026-06-06
```

## Dry Run

```bash
daily-tool-discovery dry-run --root . --date 2026-06-05
```

Artifacts:

- `candidates/YYYY-MM-DD.jsonl`
- `briefings/YYYY-MM-DD.md`

## Feedback

```bash
daily-tool-discovery feedback \
  --root . \
  --date 2026-06-05 \
  --candidate-id github:Achilng/floral-notepaper \
  --verdict tried \
  --value useful \
  --note "Good local-first small-tool sample"
```

Feedback is appended to `feedback.jsonl`.

## Design

See [docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md](docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md).
