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

Hermes integration is available through a cron-friendly script plus the bundled `daily-tool-discovery` Hermes skill. The default server install can either deliver the generated briefing directly with no LLM call, or ask Hermes to review the briefing with the skill before delivery.

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
bash scripts/install-hermes-server.sh
```

This installs the package, writes `~/.hermes/scripts/daily-tool-discovery.sh`, installs the `daily-tool-discovery` Hermes skill, and runs one smoke discovery. It does not create cron jobs.

Useful checks:

```bash
~/.hermes/scripts/daily-tool-discovery.sh
hermes skills list | grep daily-tool-discovery
```

Strongly recommended: export `GITHUB_TOKEN` before running the script. Without it, GitHub allows only a low unauthenticated API quota, and curated source metadata may fall back to empty summaries with `metadata_error_status: 403`. Curated source metadata requests are throttled by default; tune `DAILY_TOOL_DISCOVERY_GITHUB_DELAY_SECONDS` if needed.

Installed Hermes files:

- `~/.hermes/scripts/daily-tool-discovery.sh`
- `~/.hermes/skills/software-development/daily-tool-discovery/SKILL.md`

## Optional Hermes Cron

Daily Tool Discovery is intended to work with Hermes cron, but cron should be created explicitly by the user.

Cheapest mode: run the script and deliver the generated briefing without an LLM call:

```bash
hermes cron create "0 9 * * *" \
  --name daily-tool-discovery \
  --script daily-tool-discovery.sh \
  --no-agent \
  --deliver local
```

Skill review mode: let Hermes review the generated briefing with the installed skill before delivery:

```bash
hermes cron create "0 9 * * *" \
  "Review today's Daily Tool Discovery briefing. Pick at most one try item and up to two save items. Use the daily-tool-discovery skill and do not discover or install anything." \
  --name daily-tool-discovery-agent \
  --script daily-tool-discovery.sh \
  --skill daily-tool-discovery \
  --deliver local
```

Check configured jobs with `hermes cron list`.

## Discover

Run the live discovery pipeline:

```bash
daily-tool-discovery discover --root . --date 2026-06-06 --limit 80
```

By default this reads `config/sources.toml` if it exists, otherwise `config/sources.example.toml`.

Discovery combines three input paths:

- `seeds/manual.jsonl`: friend recommendations and known-good taste seeds. The server installer copies `seeds/manual.example.jsonl` here on first install. `discover` uses these seeds as ranking taste signals and filters the seed URLs out of the daily candidate list.
- `[[sources]]`: curated README-style source lists. Each source gets a capped share so one large list cannot fill the whole candidate pool.
- `[[github_search]]`: direct GitHub Search queries. `discover` reserves part of the candidate pool for search so it still runs even when source lists are large.

Artifacts:

- `candidates/YYYY-MM-DD.jsonl`
- `briefings/YYYY-MM-DD.md`

## Manual Seeds

Manual seeds are useful for friend recommendations or projects you already know about. In `discover`, they act as taste references rather than daily recommendations. Use `dry-run` only when you want to inspect the manual seeds themselves:

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
