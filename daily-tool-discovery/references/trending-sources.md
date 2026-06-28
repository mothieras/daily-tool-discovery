# Trending sources

Four signals feed the trending pool. Each has a different shape, a different
"why is this hot" answer, and a different failure mode. Don't conflate them.

The trending HTML page is scraped (no official API exists); Search-backed
sources use the same `GitHubClient` as the rest of the pipeline. The scrape
regexes live in `daily_tool_discovery/trending.py`; if GitHub ships a layout
change and a source goes empty, that's where to look first.

## 1. Daily trending (`trending-daily`)

**What it is:** `github.com/trending?since=daily` — repos GitHub surfaces for
"hot today".

**Signal:** interest *velocity*, not absolute quality. A repo can land here
on its launch day or on the day a key post hits HN/Reddit. Many of the
repos here will be small. The min_stars floor in your profile is what
keeps this honest.

**How to read it:** if a repo is on the daily list, *something* is
happening. If it's also been there for days, that's a different story
(check the daily cron output across a week — same repo appearing three
days running means it has staying power, not just a spike).

**Trust floor:** the source alone is not a quality signal. A repo with
300★ and a 1.5k-star day is more interesting than 30k★ adding 200
(percent vs. absolute).

**Failure mode:** HTML layout change → empty list. Fall back to a third-
party trending API (the `_scrape_trending` function is the only place that
needs to change). The Search API has no equivalent.

## 2. Weekly trending (`trending-weekly`)

**What it is:** `github.com/trending?since=weekly`.

**Signal:** interest over a longer window. Less spike-driven than daily.
This is where "actually growing" repos surface before they're famous.

**How to read it:** overlap with the daily list is informative — a repo
appearing on *both* daily and weekly is gaining real momentum, not just
riding a single mention. Dedupe in the candidate pool preserves the
higher-priority source label (daily > weekly), but the original metadata
is preserved too.

**Trust floor:** same as daily. Same caveat: small repos can dominate
the top of the list on a single big mention.

**Failure mode:** same as daily (HTML scrape).

## 3. New repos (`trending-new`)

**What it is:** GitHub Search `created:>YYYY-MM-DD-30d stars:>N` sorted by
stars. Default lookback: 30 days.

**Signal:** *novelty* + early interest. The best place to find tools
before they have a community, before they're on every blog.

**How to read it:** stars within 30 days of creation is a different curve
than the absolute stars on a 3-year-old project. A 200★ repo created
two weeks ago is doing something right. A 200★ repo created two years
ago is fine but unremarkable.

**Trust floor:** the pipeline's min_stars is applied to absolute stars
here too, so very-new projects (< min_stars) never make "Try Today"
unconditionally. They can still surface in Review if they match your
interests.

**Failure mode:** Search API rate limit (5000/hr authenticated). On a
busy day the source silently returns fewer items. Check the
`candidates/YYYY-MM-DD.jsonl` audit trail — each Candidate carries
`source: trending:new` if it came from here.

## 4. Fast growing (`trending-fast-growing`)

**What it is:** GitHub Search `pushed:>YYYY-MM-DD-7d` sorted by stars.
Default lookback: 7 days.

**Signal:** *proxy* for momentum. **The GitHub Search API does not expose
"stars gained in a window"** — there's no field for it. This source
approximates it with "recently active, many stars", which is correlated
but not identical. Every candidate from this source carries
`trending_proxy: pushed-window` in its metadata so consumers know the
shape of the signal.

**How to read it:** treat this as "popular and still being worked on",
not "growing fastest". A repo that gained 5000 stars in a week and
hasn't pushed since will *not* be here; a repo that gained 200 stars
this month and is shipping daily *will* be here.

**Trust floor:** same as new. The `pushed:>` filter implies maintenance
already — that's the value-add.

**Failure mode:** same Search API rate limit as `new`.

## Priority and dedupe

When a repo appears in more than one source, the higher-priority source
wins (the dedupe keeps the first match in the iteration order
`daily → weekly → new → fast-growing`). The losing source's trend signal
is *not* merged into the surviving Candidate — if you need both signals
visible, look at the raw `candidates/YYYY-MM-DD.jsonl` (one row per
source occurrence before dedupe happens).

If you want a single source's signal preserved even after dedupe, the
cleanest path is to add a "source history" field to Candidate metadata
in a follow-up — out of scope for v1.

## When to trust what

- **Daily/weekly:** trust for "what is the world excited about right
  now". Do not trust for "what should I use". Many of the repos here
  are toys, demos, or weekend hacks.
- **New repos:** trust for "what is genuinely new and worth a look".
  The fact that it was created recently and already has stars is a
  signal of *intentional* visibility (someone is sharing it, not just
  committing and forgetting).
- **Fast growing:** trust for "what is being actively maintained and
  used". The `pushed:>` filter does the maintenance work for you.
- **All four:** trust for the *candidate pool*. The trust tier
  (separate, see SKILL.md) is what decides whether a candidate
  becomes a recommendation.

## If the HTML scrape breaks

The `_ARTICLE_RE`, `_NAME_RE`, `_DESC_RE`, `_STARS_RE`, `_LANG_RE`,
`_PERIOD_BLOCK_RE` regexes in `trending.py` are the only things that
need to change. Alternative data sources to consider (in rough order
of how often they're alive):

- `https://api.gitterapp.com/repositories?since=daily`
- `https://github-trending-api.de.a9sapp.eu/`
- Community scrapers behind a Cloudflare worker

Replace `_scrape_trending` to return the same `Candidate` shape and
the rest of the pipeline keeps working.

## When to add another source

If a source gives a *different signal* (e.g. Hacker News front page,
Product Hunt launches, crates.io new releases) and you can express it
as a `Candidate` with a `source` label, add it. The trust tier and
ranking don't care where it came from; they look at the metadata. The
guidance in SKILL.md's "How to consume the briefing" still applies.
