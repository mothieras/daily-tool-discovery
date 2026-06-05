# Daily Tool Discovery Briefing Design

Date: 2026-06-05
Status: Draft for user review

## Goal

Build a server-side daily briefing workflow that finds useful tools the user would otherwise miss because they do not regularly browse social feeds.

The system focuses on:

- Agent/dev tooling: Codex, Claude Code, Hermes, MCP servers, skills, AI coding tools, terminal/dev workflow tools.
- Open-source small tools: Tauri, Electron, Rust, TypeScript, macOS, Markdown, Obsidian, CLI, and local-first utilities.

The intended taste is calibrated by examples:

- CodeIsland: agent/dev workflow companion, high-priority mainline candidate.
- Achilng/floral-notepaper: open-source, small, local-first desktop utility, secondary-line candidate.

## Non-Goals

- No paper tracking or research-topic briefing in v1.
- No generic tech news, financing news, or broad social feed replication.
- No automatic installation, subscription purchase, or workflow modification.
- No fully autonomous agent that searches, decides, and acts without inspectable intermediate artifacts.

## Recommended Shape

Use a balanced MVP:

- Mainline: 3-5 agent/dev candidates per day.
- Secondary line: 1-2 open-source small-tool candidates per day.
- Final briefing: Hermes selects at most 3 items.

The system should optimize for daily usefulness, not exhaustive discovery.

## Architecture

### Deterministic Collection Layer

Runs on the server on a daily schedule.

Responsibilities:

- Collect candidates from configured sources.
- Normalize title, URL, source, tags, repository metadata, release date, and short description.
- Deduplicate by URL, repository, and normalized name.
- Apply first-pass filters for topic fit and freshness.
- Write an inspectable candidate inbox.

The collection layer should be scriptable and debuggable. It should not depend on agent reasoning for basic fetching, parsing, deduplication, or persistence.

### Hermes Review Layer

Hermes consumes the candidate inbox and produces the daily briefing.

Responsibilities:

- Score fit against the user's current workflow.
- Explain why each selected item matters.
- Classify each selected item as try, save, or ignore.
- Keep the output short enough to read daily.
- Use manual seed examples as high-weight taste signals.

Hermes should not directly install tools or mutate the user's environment in v1.

### Storage

Use simple local files first:

- `candidates/YYYY-MM-DD.jsonl`: normalized raw candidates.
- `briefings/YYYY-MM-DD.md`: final daily briefing.
- `seeds/manual.jsonl`: manually supplied examples and recommendations.
- `feedback.jsonl`: user feedback on try/save/ignore decisions.

This keeps the first version easy to inspect, back up, and hand to Hermes.

## Candidate Sources

v1 should start with a small source set:

- GitHub search or topic feeds for agent/dev and local-first tool categories.
- GitHub releases or trending-like discovery for recently active projects.
- MCP and agent tool directories when available.
- Skill/plugin ecosystems relevant to Codex, Claude Code, Obsidian, and Hermes.
- Manual seeds from friends or the user.

Manual seeds should carry the highest weight because they directly express the taste profile.

## Filtering Criteria

A candidate is more valuable when it is:

- Directly useful to the user's Codex, Hermes, agent, or dev workflow.
- Open source or locally inspectable.
- Installable or testable in 15-30 minutes.
- Recently active or has clear maintenance signals.
- Small enough to understand without committing to a large platform.
- Similar in spirit to CodeIsland or floral-notepaper.

A candidate should be downranked when it is:

- Pure marketing with no usable artifact.
- A generic AI wrapper with unclear differentiation.
- A research paper or topic trend rather than a tool.
- Too broad, enterprise-heavy, or impossible to test quickly.

## Daily Briefing Format

Each briefing should contain at most three selected items:

```md
# Daily Tool Discovery Briefing - YYYY-MM-DD

## Try Today

### <tool name>
- Link:
- Type:
- Why it matters:
- Why now:
- 15-minute trial:
- Risk or caveat:

## Save

### <tool name>
- Link:
- Type:
- Why it is worth saving:
- When to revisit:

## Ignore

### <tool name or pattern>
- Link:
- Reason:
- Filter lesson:
```

If no item deserves "Try Today", the system should say so rather than forcing one.

## Feedback Loop

The user should be able to add lightweight feedback:

- `tried`: useful, not useful, blocked, already known.
- `saved`: worth tracking, not relevant, duplicate.
- `ignored`: correct ignore, false negative.
- Free-text note.

Feedback updates future ranking but does not need a complex model in v1. A simple JSONL log plus prompt context is enough.

## Operational Model

Target deployment is the user's server.

Suggested first operating mode:

- A daily timer runs the collector.
- The collector writes candidates.
- Hermes reads the candidate file and writes the briefing.
- The briefing is saved as Markdown and optionally sent via an existing notification path.

The initial implementation should expose dry-run commands so the user can inspect candidates before enabling the daily timer.

## Success Criteria

v1 is successful when:

- It produces a readable daily Markdown briefing.
- The briefing contains at most three items.
- At least one item per several days is genuinely worth trying or saving.
- The user can manually seed examples and see future recommendations shift.
- Every selected item can be traced back to a source URL and candidate record.
- Failures are inspectable from local files or logs.

## Open Decisions For Planning

- Exact source list for the first week.
- Whether the delivery target is a Markdown file only, Hermes inbox, notification, or all three.
- Server path and schedule time.
- Hermes invocation interface on the server.
- Whether to include public web search in v1 or start with API/feed sources only.
