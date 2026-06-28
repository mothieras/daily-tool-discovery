"""GitHub Trending as a candidate source.

Pulls from four signals — daily trending, weekly trending, recently-created
repos, and fast-growing repos — and normalizes them into ``Candidate`` objects
that flow through the existing trust tier + ranking pipeline unchanged.

There is no official API for github.com/trending, so daily/weekly are scraped
from the HTML page (reusing ``UrllibTextTransport``). New/fast-growing use the
official GitHub Search API via the shared ``GitHubClient``. If the HTML layout
ever changes and scraping breaks, see ``references/trending-sources.md`` for the
fallback plan (swap in a third-party trending API).
"""

from __future__ import annotations

import html
import re
import sys
from datetime import date as date_type, timedelta

from daily_tool_discovery.curated_sources import TextTransport, UrllibTextTransport
from daily_tool_discovery.github_client import GitHubClient
from daily_tool_discovery.models import Candidate

# Public, ordered by dedupe priority: an earlier source wins when a repo shows
# up in more than one (daily's per-day signal is the richest, so it comes first).
TRENDING_SOURCES: tuple[str, ...] = ("daily", "weekly", "new", "fast-growing")

TRENDING_BASE_URL = "https://github.com/trending"

# Default lookback windows for the search-backed sources (days).
NEW_REPO_WINDOW_DAYS = 30
FAST_GROWING_WINDOW_DAYS = 7

# Metadata keys that carry the trending signal itself (vs. plain repo metadata).
# Preserved when a scraped repo is enriched with live API metadata.
_TRENDING_META_KEYS = ("trending_source", "trending_rank", "stars_today", "weekly_growth", "trending_proxy")

_ARTICLE_RE = re.compile(r'<article class="Box-row">(.*?)</article>', re.DOTALL)
_NAME_RE = re.compile(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+)"', re.DOTALL)
_DESC_RE = re.compile(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', re.DOTALL)
_STARS_RE = re.compile(r'href="/[^"]+/stargazers"[^>]*>(.*?)</a>', re.DOTALL)
_LANG_RE = re.compile(r'itemprop="programmingLanguage">\s*([^<]+?)\s*</span>')
_PERIOD_BLOCK_RE = re.compile(r'float-sm-right[^>]*>(.*?)</span>', re.DOTALL)
_PERIOD_NUM_RE = re.compile(r'([\d,]+)\s+stars?\s+(?:today|this week)')


def discover_trending_candidates(
    github_client: GitHubClient,
    discovered_at: str,
    *,
    daily_limit: int = 25,
    weekly_limit: int = 25,
    new_repos_limit: int = 15,
    fast_growing_limit: int = 15,
    min_stars: int = 50,  # floor to avoid spam
    language: str | None = None,
    text_transport: TextTransport | None = None,
) -> list[Candidate]:
    """Pull from 4 trending sources, normalize, return as Candidates.

    Daily/weekly trending are scraped, then enriched via the GitHub API so the
    trust tier has full metadata (created/pushed dates, forks, owner) — without
    it, scraped repos could never reach the ``trusted`` tier. New/fast-growing
    come from Search with complete metadata already. Result is deduped across
    sources (priority order in ``TRENDING_SOURCES``) and floored at ``min_stars``.
    """
    grouped = gather_trending(
        github_client,
        discovered_at,
        want=TRENDING_SOURCES,
        limits={
            "daily": daily_limit,
            "weekly": weekly_limit,
            "new": new_repos_limit,
            "fast-growing": fast_growing_limit,
        },
        min_stars=min_stars,
        language=language,
        text_transport=text_transport,
    )

    by_id: dict[str, Candidate] = {}
    for source in TRENDING_SOURCES:
        for candidate in grouped.get(source, []):
            if candidate.id.lower() in by_id:
                continue
            if source in ("daily", "weekly"):
                enriched = _enrich(candidate, github_client, discovered_at)
                if enriched is None:
                    print(
                        f"WARN [trending]: dropped {candidate.name} — enrichment failed "
                        "(no live metadata for the trust tier)",
                        file=sys.stderr,
                    )
                    continue
                candidate = enriched
            by_id[candidate.id.lower()] = candidate
    return list(by_id.values())


def gather_trending(
    github_client: GitHubClient,
    discovered_at: str,
    *,
    want: tuple[str, ...] | list[str] | set[str],
    limits: dict[str, int],
    min_stars: int = 50,
    language: str | None = None,
    since_days: int | None = None,
    text_transport: TextTransport | None = None,
) -> dict[str, list[Candidate]]:
    """Gather raw (un-enriched) candidates per requested source.

    This is the read path shared by ``discover`` and the ``browse`` CLI command:
    it never makes the per-repo metadata calls that enrichment does, so it stays
    cheap and deterministic. Returns ``{source: [Candidate, ...]}`` for each
    requested source, each list already floored at ``min_stars``.
    """
    transport = text_transport or UrllibTextTransport()
    grouped: dict[str, list[Candidate]] = {}
    for source in want:
        limit = max(0, int(limits.get(source, 0)))
        if limit <= 0:
            continue
        try:
            if source == "daily":
                items = _scrape_trending(transport, "daily", language, discovered_at, limit, min_stars)
            elif source == "weekly":
                items = _scrape_trending(transport, "weekly", language, discovered_at, limit, min_stars)
            elif source == "new":
                items = _search_new(github_client, discovered_at, limit, min_stars, language, since_days)
            elif source == "fast-growing":
                items = _search_fast_growing(github_client, discovered_at, limit, min_stars, language, since_days)
            else:
                continue
        except Exception as exc:  # one bad source must not sink the others
            print(f"WARN [trending]: source {source!r} failed: {exc}", file=sys.stderr)
            items = []
        grouped[source] = items
    return grouped


# --- daily / weekly: scrape the HTML trending page -------------------------


def _scrape_trending(
    transport: TextTransport,
    since: str,
    language: str | None,
    discovered_at: str,
    limit: int,
    min_stars: int,
) -> list[Candidate]:
    url = _trending_url(since, language)
    html_text = transport.get_text(url)
    candidates: list[Candidate] = []
    for rank, block in enumerate(_ARTICLE_RE.findall(html_text), start=1):
        name_match = _NAME_RE.search(block)
        if not name_match:
            continue
        full_name = _normalize_full_name(name_match.group(1))
        if not full_name:
            continue
        # Strip tags before reading digits: the SVG star icon carries
        # height="16"/width="16" attrs that would otherwise pollute the count.
        stars = _parse_int(_clean_text(_first_group(_STARS_RE, block)))
        if stars < min_stars:
            continue
        period_stars = _parse_period_stars(block)
        metric_key = "stars_today" if since == "daily" else "weekly_growth"
        metadata = {
            "stars": stars,
            "trending_source": since,
            "trending_rank": rank,
            "language": _clean_text(_first_group(_LANG_RE, block)) or None,
        }
        if period_stars is not None:
            metadata[metric_key] = period_stars
        candidates.append(
            Candidate(
                id=f"github:{full_name}",
                name=full_name,
                url=f"https://github.com/{full_name}",
                source=f"trending:{since}",
                summary=_clean_text(_first_group(_DESC_RE, block)),
                tags=[],
                kind=f"trending-{since}",
                discovered_at=discovered_at,
                metadata=metadata,
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def _trending_url(since: str, language: str | None) -> str:
    from urllib.parse import quote

    path = TRENDING_BASE_URL
    if language:
        path = f"{TRENDING_BASE_URL}/{quote(language.strip().lower())}"
    return f"{path}?since={since}"


# --- new / fast-growing: official GitHub Search API -------------------------


def _search_new(
    github_client: GitHubClient,
    discovered_at: str,
    limit: int,
    min_stars: int,
    language: str | None,
    since_days: int | None,
) -> list[Candidate]:
    days = since_days if since_days is not None else NEW_REPO_WINDOW_DAYS
    cutoff = _cutoff(discovered_at, days)
    query = f"created:>{cutoff}"
    if language:
        query = f"{query} language:{language}"
    found = github_client.search_repositories(
        query=query, discovered_at=discovered_at, kind="trending-new",
        per_page=limit, min_stars=min_stars, sort="stars", order="desc",
    )
    return [_relabel(c, "trending:new", trending_source="new") for c in found]


def _search_fast_growing(
    github_client: GitHubClient,
    discovered_at: str,
    limit: int,
    min_stars: int,
    language: str | None,
    since_days: int | None,
) -> list[Candidate]:
    # Proxy: GitHub Search exposes no "stars gained in a window", so surface
    # recently-pushed popular repos (sorted by stars). Labelled so consumers
    # know it is an approximation — see references/trending-sources.md.
    days = since_days if since_days is not None else FAST_GROWING_WINDOW_DAYS
    cutoff = _cutoff(discovered_at, days)
    query = f"pushed:>{cutoff}"
    if language:
        query = f"{query} language:{language}"
    found = github_client.search_repositories(
        query=query, discovered_at=discovered_at, kind="trending-fast-growing",
        per_page=limit, min_stars=min_stars, sort="stars", order="desc",
    )
    return [
        _relabel(c, "trending:fast-growing", trending_source="fast-growing", trending_proxy="pushed-window")
        for c in found
    ]


# --- enrichment + helpers ---------------------------------------------------


def _enrich(candidate: Candidate, github_client: GitHubClient, discovered_at: str) -> Candidate | None:
    """Backfill live repo metadata for a scraped repo, keeping the trend signal.

    On failure, return ``None`` so the caller drops the repo. A scraped-only
    Candidate has no created/pushed/forks/owner, so the trust tier would compute
    "unknown" everywhere and the repo would land in the briefing with junk
    metadata — a worse signal than no Candidate at all.
    """
    overlay = {k: candidate.metadata[k] for k in _TRENDING_META_KEYS if k in candidate.metadata}
    try:
        enriched = github_client.get_repository(
            full_name=candidate.name,
            discovered_at=discovered_at,
            kind=candidate.kind,
            source=candidate.source,
        )
    except Exception:
        return None
    return enriched.with_metadata(**overlay)


def _relabel(candidate: Candidate, source: str, **extra: object) -> Candidate:
    return Candidate(
        id=candidate.id,
        name=candidate.name,
        url=candidate.url,
        source=source,
        summary=candidate.summary,
        tags=candidate.tags,
        kind=candidate.kind,
        discovered_at=candidate.discovered_at,
        metadata={**dict(candidate.metadata), **extra},
    )


def _cutoff(discovered_at: str, days: int) -> str:
    return (date_type.fromisoformat(discovered_at) - timedelta(days=max(0, days))).isoformat()


def _normalize_full_name(href_path: str) -> str:
    parts = [p for p in href_path.strip("/").split("/") if p]
    if len(parts) < 2:
        return ""
    return f"{parts[0]}/{parts[1]}"


def _first_group(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1) if match else ""


def _parse_int(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else 0


def _parse_period_stars(block: str) -> int | None:
    period_block = _clean_text(_first_group(_PERIOD_BLOCK_RE, block))
    if not period_block:
        return None
    num = _PERIOD_NUM_RE.search(period_block)
    return _parse_int(num.group(1)) if num else None


def _clean_text(raw: str) -> str:
    if not raw:
        return ""
    stripped = re.sub(r"<[^>]+>", " ", raw)
    return " ".join(html.unescape(stripped).split())


# --- browse rendering (raw Markdown snapshot, no trust/ranking/LLM) ---------

_SECTION_TITLES = {
    "daily": "Daily trending",
    "weekly": "Weekly trending",
    "new": "New repos (recently created)",
    "fast-growing": "Fast growing (proxy: recently pushed, by stars)",
}


def render_browse_markdown(
    discovered_at: str,
    grouped: dict[str, list[Candidate]],
    *,
    order: tuple[str, ...] | list[str] = TRENDING_SOURCES,
    min_stars: int = 50,
) -> str:
    lines = [f"# Trending snapshot — {discovered_at}", ""]
    lines.append(
        f"_Raw GitHub trending data — no trust tier, ranking, or LLM. min_stars floor: {min_stars}._"
    )
    lines.append("")
    for source in order:
        if source not in grouped:
            continue
        lines.append(f"## {_SECTION_TITLES.get(source, source)}")
        items = grouped[source]
        if not items:
            lines.append("")
            lines.append("_No repos right now._")
            lines.append("")
            continue
        for rank, candidate in enumerate(items, start=1):
            lines.extend(_render_item(rank, candidate))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_item(rank: int, candidate: Candidate) -> list[str]:
    md = candidate.metadata
    facts = []
    growth = _growth_label(md)
    if growth:
        facts.append(growth)
    stars = int(md.get("stars") or 0)
    if stars:
        facts.append(f"{stars:,}★")
    language = md.get("language")
    if language:
        facts.append(str(language))
    fact_line = " · ".join(facts)
    header = f"{rank}. **{candidate.name}**"
    if fact_line:
        header += f" — {fact_line}"
    out = [header, f"   {candidate.url}"]
    if candidate.summary:
        out.append(f"   {candidate.summary}")
    return out


def _growth_label(md) -> str:
    if md.get("stars_today") is not None:
        return f"{int(md['stars_today']):,} stars today"
    if md.get("weekly_growth") is not None:
        return f"{int(md['weekly_growth']):,} stars this week"
    if md.get("trending_proxy") == "pushed-window":
        return "recently pushed"
    if md.get("trending_source") == "new":
        return "newly created"
    return ""
