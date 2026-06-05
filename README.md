# Daily Tool Discovery

Daily Tool Discovery is a server-side briefing workflow for finding useful tools without relying on social feeds.

The project focuses on:

- Agent/dev tooling: Codex, Claude Code, Hermes, MCP servers, skills, AI coding tools, terminal/dev workflow tools.
- Open-source small tools: Tauri, Electron, Rust, TypeScript, macOS, Markdown, Obsidian, CLI, and local-first utilities.

The intended v1 shape is a deterministic collector plus a Hermes review layer:

- Collect and normalize candidate tools.
- Deduplicate and filter candidates.
- Let Hermes score, explain, and select a short daily briefing.
- Save inspectable Markdown and JSONL artifacts.

See [docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md](docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md).
