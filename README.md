# Daily Tool Discovery

**Trust-first daily tool discovery: surfaces vetted dev/CLI tools, filters spam & malware, and learns a taste profile you fully control.**

Daily Tool Discovery is a server-side briefing workflow for finding useful tools without
doomscrolling social feeds. It runs on a schedule, collects candidate projects, judges
them by **community and maintenance trust before relevance**, and writes a short,
inspectable Markdown briefing each day.

It exists because the naive version of this idea fails in two ways: it recommends
keyword-stuffed spam/malware (a scorer that only rewards topic matches loves an
LLM-generated README), and it shows you the same popular repos every day. This pipeline is
built to avoid both.

## Why it's different

- **Trust before relevance.** Every candidate gets a tier — `trusted` / `review` /
  `reject` — from stars, forks, issues/PRs, maintenance recency, and publisher
  credibility. A repo below your star floor can **never** be a "Try Today" pick no matter
  how perfectly it matches keywords. Auto-generated usernames + 0 stars/forks + hollow
  READMEs are quarantined.
- **Configurable taste.** What counts as relevant lives in `config/profile.toml`, not in
  code. Edit categories, their signal tags, weights, and sources to **retarget the tool to
  any domain** — see `config/profiles/web-frontend.example.toml`.
- **It won't repeat itself.** Items you've already been shown cool down for a novelty
  window, so the daily briefing actually rotates.
- **It learns, carefully.** Saving a project gently biases future picks toward similar
  tools — but the learning loop is deliberately weak, capped, and decaying, and every
  briefing reserves a **🎲 Explore** slot for a deliberately off-profile pick, so it can't
  collapse into a filter bubble.
- **Deterministic and inspectable.** Ranking is plain rules (no LLM required); every
  decision traces back to a JSONL record you can read.

## How it works

```
collect (curated awesome-lists + GitHub search)
  → trust-tier each candidate (trusted / review / reject)
  → score (community/maintenance dominate; profile relevance + learned taste nudge)
  → select into buckets, drop denied/saved/recently-seen
  → write Markdown briefing + JSONL inbox
```

A briefing has five sections:

- **Try Today** / **Save** — trust-vetted picks that match your profile.
- **Review yourself** — on-topic but low community signal; audit before running.
- **🎲 Explore** — one deliberately off-profile, trust-vetted pick to break the filter bubble.
- A footer reports how many suspicious candidates were filtered out.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Discover

```bash
daily-tool-discovery discover --root . --date 2026-06-06 --limit 80
```

By default this reads `config/profile.toml` if it exists, otherwise
`config/profile.example.toml`. Discovery combines three input paths:

- `seeds/manual.jsonl`: friend recommendations and known-good taste seeds. The server
  installer copies `seeds/manual.example.jsonl` here on first install. `discover` uses
  these as taste references and filters the seed URLs out of the daily candidate list.
- `[[category.source]]`: curated README-style source lists (awesome-lists). Each source
  gets a capped share so one large list cannot fill the whole candidate pool.
- `[[category.search]]`: direct GitHub Search queries (topic- and time-bounded for fresh
  discovery). `discover` reserves part of the pool for search.

Artifacts:

- `candidates/YYYY-MM-DD.jsonl` — the full discovered inbox, annotated with trust tier and
  risk flags (traceable; nothing is silently dropped).
- `briefings/YYYY-MM-DD.md` — the rendered daily briefing.

Export `GITHUB_TOKEN` before running. Without it GitHub allows only a low unauthenticated
quota, and curated metadata can fall back to empty summaries with
`metadata_error_status: 403`. Metadata requests are throttled by default; tune
`DAILY_TOOL_DISCOVERY_GITHUB_DELAY_SECONDS` if needed.

## The taste profile

Taste is data, not code. `config/profile.toml` (falling back to
`config/profile.example.toml`) defines everything:

```toml
[[category]]
name = "agent-dev"
weight = 2                       # mainline emphasis
signal_tags = ["mcp", "agent", "claude-code", "skill"]
  [[category.source]]
  name = "awesome-mcp-servers"
  url = "https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md"
  [[category.search]]
  name = "fresh-agent-tools"
  query = "topic:mcp created:>2026-03-01"
  min_stars = 50

[trust]                          # stars floor, novelty window, freshness
min_stars = 20
novelty_days = 30

[recommend]                      # the learning-loop guardrails
taste_max_points = 12            # learned taste is a capped nudge
learn_last_n_saves = 20          # decay: only recent saves count
cold_start_min_saves = 5         # no learning until enough saves
explore_slots = 1                # forced off-profile exposure

[lists]
deny = ["someowner/*"]           # never surface (also see denylist.txt)
```

Relevance is **pure tags**: a candidate's topics/name/summary are matched against each
category's `signal_tags`, weighted by `weight`, and capped — so relevance can order
trusted candidates but never override the trust floor. To hunt a different domain, copy a
profile and edit its categories.

## Commands

```bash
# Save a project: bookmark it, stop re-recommending it, gently bias future picks.
daily-tool-discovery save --root . --candidate-id github:owner/repo

# Deny a project or owner (glob): never surface it again. Appends to denylist.txt.
daily-tool-discovery deny --root . --pattern owner/repo

# Lightweight feedback (tried / saved / ignored). Appended to feedback.jsonl.
daily-tool-discovery feedback \
  --root . \
  --date 2026-06-06 \
  --candidate-id github:owner/repo \
  --verdict tried \
  --value useful \
  --note "Worth keeping"
```

Trust and recommender knobs can also be set via flags
(`--min-stars`/`DAILY_TOOL_DISCOVERY_MIN_STARS`,
`--novelty-days`/`DAILY_TOOL_DISCOVERY_NOVELTY_DAYS`) or the profile's `[trust]`/`[recommend]`.

## Manual seeds and dry run

Manual seeds are for friend recommendations or projects you already know. In `discover`
they act as taste references rather than daily recommendations. Use `dry-run` to inspect
the seeds themselves:

```bash
mkdir -p seeds
cp seeds/manual.example.jsonl seeds/manual.jsonl
daily-tool-discovery dry-run --root . --date 2026-06-06
```

`dry-run` writes the same artifacts (`candidates/YYYY-MM-DD.jsonl`,
`briefings/YYYY-MM-DD.md`) from the manual seeds only.

## Hermes integration

Hermes integration is available through a cron-friendly script plus the bundled
`daily-tool-discovery` Hermes skill. The skill teaches an agent both *what makes a good
project* (the trust method) and *how to operate the pipeline* (edit the profile, save,
deny). The default server install can deliver the generated briefing directly with
no LLM call, or ask Hermes to review it with the skill first.

On a server with Hermes and the GitHub CLI logged in:

```bash
mkdir -p ~/apps
gh repo clone mothieras/daily-tool-discovery ~/apps/daily-tool-discovery
cd ~/apps/daily-tool-discovery
bash scripts/install-hermes-server.sh
```

This installs the package, copies `config/profile.example.toml` to `config/profile.toml`,
writes `~/.hermes/scripts/daily-tool-discovery.sh`, installs the skill, and runs one smoke
discovery. It does not create cron jobs. Useful checks:

```bash
~/.hermes/scripts/daily-tool-discovery.sh
hermes skills list | grep daily-tool-discovery
```

### Optional Hermes Cron

Cron should be created explicitly by the user. Cheapest mode — run the script and deliver
the briefing without an LLM call:

```bash
hermes cron create "0 9 * * *" \
  --name daily-tool-discovery \
  --script daily-tool-discovery.sh \
  --no-agent \
  --deliver local
```

Skill-review mode — let Hermes review the briefing with the installed skill first:

```bash
hermes cron create "0 9 * * *" \
  "Review today's Daily Tool Discovery briefing. Pick at most one try item and up to two save items. Use the daily-tool-discovery skill and do not discover or install anything." \
  --name daily-tool-discovery-agent \
  --script daily-tool-discovery.sh \
  --skill daily-tool-discovery \
  --deliver local
```

Check configured jobs with `hermes cron list`.

## Design notes

The original design rationale (historical; the pipeline has since gained trust gating, a
configurable profile, and the Explore slot) lives in
[docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md](docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md).
