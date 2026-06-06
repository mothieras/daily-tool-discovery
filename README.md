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

Hermes invocation is not wired yet. `prompts/hermes-review.md` is a review prompt/interface artifact for a later integration, not something the current CLI executes. Today, `dry-run` uses local manual seeds and deterministic ranking to write the candidate and briefing artifacts below.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Manual Seeds

Copy the example seed file before the first dry run:

```bash
mkdir -p seeds
cp seeds/manual.example.jsonl seeds/manual.jsonl
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
