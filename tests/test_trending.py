"""Unit tests for the GitHub Trending candidate source.

All four signals are exercised with fakes — no real network is touched.
Daily/weekly are driven through ``FakeTextTransport`` (canned HTML), and
new/fast-growing through ``RecordingGitHubClient`` (records the Search query
and returns canned candidates).
"""

from daily_tool_discovery.models import Candidate
from daily_tool_discovery.trending import (
    NEW_REPO_WINDOW_DAYS,
    FAST_GROWING_WINDOW_DAYS,
    _parse_period_stars,
    _scrape_trending,
    _search_fast_growing,
    _search_new,
    discover_trending_candidates,
    render_browse_markdown,
)

DISCOVERED_AT = "2026-06-28"


# --- fakes ------------------------------------------------------------------


class FakeTextTransport:
    """Returns the same HTML for any URL (mirrors test_curated_sources)."""

    def __init__(self, text):
        self.text = text

    def get_text(self, url):
        return self.text


class FakeTextTransportByUrl:
    """Per-URL HTML; raise an exception value to simulate a failing fetch."""

    def __init__(self, texts):
        self.texts = texts

    def get_text(self, url):
        value = self.texts[url]
        if isinstance(value, Exception):
            raise value
        return value


class RecordingGitHubClient:
    """Records search calls and returns canned repos. Also enriches via
    ``get_repository`` so the scraped daily/weekly path can be exercised."""

    def __init__(self, search_results=None):
        self.search_results = search_results or []
        self.search_calls = []
        self.repo_calls = []

    def search_repositories(self, query, discovered_at, kind, per_page=10,
                            min_stars=0, sort="updated", order="desc"):
        self.search_calls.append(
            {"query": query, "kind": kind, "per_page": per_page,
             "min_stars": min_stars, "sort": sort, "order": order}
        )
        return [
            Candidate(
                id=f"github:{name}", name=name, url=f"https://github.com/{name}",
                source="github", summary="found via search", tags=["mcp"], kind=kind,
                discovered_at=discovered_at, metadata={"stars": 321, "language": "Go"},
            )
            for name in self.search_results
        ]

    def get_repository(self, full_name, discovered_at, kind, source):
        self.repo_calls.append(full_name)
        return Candidate(
            id=f"github:{full_name}", name=full_name, url=f"https://github.com/{full_name}",
            source=source, summary="enriched summary", tags=["mcp"], kind=kind,
            discovered_at=discovered_at,
            metadata={"stars": 999, "language": "Rust", "owner_login": full_name.split("/")[0]},
        )


# --- HTML fixture builder ---------------------------------------------------


def _article(full_name, stars, *, period=None, period_label="today",
             language="Python", description="A handy tool"):
    """Build one representative <article class="Box-row"> block.

    The stargazers anchor wraps an SVG star icon carrying height="16"/width="16"
    plus a <path d="..."> full of digits — exactly the noise _STARS_RE/_clean_text
    must strip past before reading the real star count.
    """
    owner, repo = full_name.split("/")
    period_html = ""
    if period is not None:
        period_html = (
            '<span class="d-inline-block float-sm-right">'
            '<svg aria-hidden="true" height="16" width="16" viewBox="0 0 16 16">'
            '<path d="M8 .25a.75 1 234 567"></path></svg>'
            f"{period} stars {period_label}"
            "</span>"
        )
    lang_html = ""
    if language:
        lang_html = f'<span itemprop="programmingLanguage">{language}</span>'
    return (
        '<article class="Box-row">'
        f'<h2 class="h3 lh-condensed"><a href="/{full_name}" data-hydro-click="x">'
        f"<span>{owner} /</span> {repo}</a></h2>"
        f'<p class="col-9 color-fg-muted my-1 pr-4">{description}</p>'
        '<div class="f6 color-fg-muted mt-2">'
        f'<a href="/{full_name}/stargazers" class="Link--muted d-inline-block mr-3">'
        '<svg aria-hidden="true" height="16" width="16" viewBox="0 0 16 16">'
        '<path d="M8 .25a.75 16 16 99999"></path></svg>'
        f" {stars:,} </a>"
        f"{lang_html}{period_html}"
        "</div>"
        "</article>"
    )


def _page(*articles):
    return '<html><body><div class="Box">' + "".join(articles) + "</div></body></html>"


# --- _scrape_trending -------------------------------------------------------


def test_scrape_parses_representative_article_block():
    html = _page(_article("octocat/hello", 12_345, period=678, language="Python"))
    out = _scrape_trending(FakeTextTransport(html), "daily", None, DISCOVERED_AT, 25, 50)

    assert len(out) == 1
    c = out[0]
    assert c.id == "github:octocat/hello"
    assert c.name == "octocat/hello"
    assert c.url == "https://github.com/octocat/hello"
    assert c.source == "trending:daily"
    assert c.summary == "A handy tool"
    # SVG height/width="16" and the path digits must NOT pollute the star count.
    assert c.metadata["stars"] == 12_345
    assert c.metadata["language"] == "Python"
    assert c.metadata["trending_source"] == "daily"
    assert c.metadata["trending_rank"] == 1
    assert c.metadata["stars_today"] == 678  # daily -> stars_today


def test_scrape_weekly_uses_weekly_growth_metric():
    html = _page(_article("a/weekly", 5_000, period=900, period_label="this week"))
    out = _scrape_trending(FakeTextTransport(html), "weekly", None, DISCOVERED_AT, 25, 50)

    assert out[0].source == "trending:weekly"
    assert out[0].metadata["weekly_growth"] == 900
    assert "stars_today" not in out[0].metadata


def test_scrape_honors_min_stars_floor():
    html = _page(
        _article("low/repo", 30),   # below floor -> dropped
        _article("high/repo", 80),  # above floor -> kept
    )
    out = _scrape_trending(FakeTextTransport(html), "daily", None, DISCOVERED_AT, 25, 50)

    names = [c.name for c in out]
    assert names == ["high/repo"]


def test_scrape_honors_limit():
    html = _page(*[_article(f"owner/repo{i}", 100 + i) for i in range(6)])
    out = _scrape_trending(FakeTextTransport(html), "daily", None, DISCOVERED_AT, 3, 50)

    assert len(out) == 3


def test_scrape_returns_empty_when_no_articles():
    html = "<html><body><p>github trending is empty today</p></body></html>"
    out = _scrape_trending(FakeTextTransport(html), "daily", None, DISCOVERED_AT, 25, 50)

    assert out == []


# --- _parse_period_stars ----------------------------------------------------


def test_parse_period_stars_today():
    block = _article("a/b", 100, period="1,234", period_label="today")
    assert _parse_period_stars(block) == 1234


def test_parse_period_stars_this_week():
    block = _article("a/b", 100, period="456", period_label="this week")
    assert _parse_period_stars(block) == 456


def test_parse_period_stars_absent_returns_none():
    block = _article("a/b", 100, period=None)
    assert _parse_period_stars(block) is None


# --- _search_new / _search_fast_growing -------------------------------------


def test_search_new_builds_created_query_with_default_window():
    client = RecordingGitHubClient(search_results=["new/repo"])
    out = _search_new(client, DISCOVERED_AT, 15, 50, None, None)

    # default window = NEW_REPO_WINDOW_DAYS (30) before 2026-06-28 -> 2026-05-29
    assert NEW_REPO_WINDOW_DAYS == 30
    assert client.search_calls[0]["query"] == "created:>2026-05-29"
    assert client.search_calls[0]["sort"] == "stars"
    assert client.search_calls[0]["order"] == "desc"
    assert out[0].source == "trending:new"
    assert out[0].metadata["trending_source"] == "new"


def test_search_new_applies_language_filter_and_since_days():
    client = RecordingGitHubClient(search_results=["new/repo"])
    _search_new(client, DISCOVERED_AT, 15, 50, "python", 7)

    # explicit since_days=7 overrides the default window -> 2026-06-21
    assert client.search_calls[0]["query"] == "created:>2026-06-21 language:python"


def test_search_fast_growing_builds_pushed_query_with_proxy_metadata():
    client = RecordingGitHubClient(search_results=["fast/repo"])
    out = _search_fast_growing(client, DISCOVERED_AT, 15, 50, None, None)

    # default window = FAST_GROWING_WINDOW_DAYS (7) before 2026-06-28 -> 2026-06-21
    assert FAST_GROWING_WINDOW_DAYS == 7
    assert client.search_calls[0]["query"] == "pushed:>2026-06-21"
    assert out[0].source == "trending:fast-growing"
    assert out[0].metadata["trending_source"] == "fast-growing"
    assert out[0].metadata["trending_proxy"] == "pushed-window"


def test_search_fast_growing_applies_language_filter():
    client = RecordingGitHubClient(search_results=["fast/repo"])
    _search_fast_growing(client, DISCOVERED_AT, 15, 50, "rust", None)

    assert client.search_calls[0]["query"] == "pushed:>2026-06-21 language:rust"


# --- discover_trending_candidates (public entry point) ----------------------


def test_discover_dedupes_across_daily_and_weekly_daily_wins():
    # foo/bar appears in both daily and weekly; daily is higher priority.
    daily_html = _page(_article("foo/bar", 500, period=88))
    weekly_html = _page(_article("foo/bar", 500, period=300, period_label="this week"))
    transport = FakeTextTransportByUrl(
        {
            "https://github.com/trending?since=daily": daily_html,
            "https://github.com/trending?since=weekly": weekly_html,
        }
    )
    client = RecordingGitHubClient(search_results=[])  # new/fast-growing return nothing

    out = discover_trending_candidates(
        client, DISCOVERED_AT, min_stars=50, text_transport=transport,
    )

    matches = [c for c in out if c.id == "github:foo/bar"]
    assert len(matches) == 1
    # daily's signal wins the dedupe
    assert matches[0].metadata["trending_source"] == "daily"
    assert matches[0].metadata["stars_today"] == 88


def test_discover_floors_below_min_stars():
    html = _page(_article("low/repo", 30), _article("ok/repo", 200))
    transport = FakeTextTransport(html)
    client = RecordingGitHubClient(search_results=[])

    out = discover_trending_candidates(
        client, DISCOVERED_AT, min_stars=50, text_transport=transport,
    )

    names = {c.name for c in out}
    assert "ok/repo" in names
    assert "low/repo" not in names


def test_discover_empty_when_all_sources_empty():
    transport = FakeTextTransport("<html><body>nothing here</body></html>")
    client = RecordingGitHubClient(search_results=[])

    out = discover_trending_candidates(
        client, DISCOVERED_AT, min_stars=50, text_transport=transport,
    )

    assert out == []


def test_discover_degrades_gracefully_when_one_source_fails(capsys):
    # Daily fetch raises; weekly still returns. The WARN path in gather_trending
    # must swallow daily's failure and let weekly through.
    transport = FakeTextTransportByUrl(
        {
            "https://github.com/trending?since=daily": RuntimeError("layout changed"),
            "https://github.com/trending?since=weekly": _page(_article("weekly/survivor", 400)),
        }
    )
    client = RecordingGitHubClient(search_results=[])

    out = discover_trending_candidates(
        client, DISCOVERED_AT, min_stars=50, text_transport=transport,
    )

    assert any(c.name == "weekly/survivor" for c in out)
    assert "WARN [trending]" in capsys.readouterr().err


def test_discover_drops_scraped_repo_when_enrichment_fails(capsys):
    # A scraped daily repo whose enrichment call fails must be dropped, not
    # surfaced with scrape-only (no created/pushed/forks/owner) metadata. One
    # WARN line naming the repo — no stack trace.
    transport = FakeTextTransportByUrl(
        {
            "https://github.com/trending?since=daily": _page(_article("ghost/repo", 400)),
            "https://github.com/trending?since=weekly": _page(),
        }
    )

    class FailingEnrichClient(RecordingGitHubClient):
        def get_repository(self, full_name, discovered_at, kind, source):
            raise RuntimeError("repo metadata fetch failed")

    out = discover_trending_candidates(
        FailingEnrichClient(search_results=[]), DISCOVERED_AT,
        min_stars=50, text_transport=transport,
    )

    assert out == []  # scraped-only candidate dropped rather than fed to the trust tier
    err = capsys.readouterr().err
    assert "WARN [trending]" in err
    assert "ghost/repo" in err


# --- render_browse_markdown -------------------------------------------------


def _browse_candidate(name, *, stars, language, source, **extra_meta):
    meta = {"stars": stars, "language": language}
    meta.update(extra_meta)
    return Candidate(
        id=f"github:{name}", name=name, url=f"https://github.com/{name}",
        source=source, summary="does a thing", tags=[], kind="trending",
        discovered_at=DISCOVERED_AT, metadata=meta,
    )


def test_render_browse_markdown_structure():
    grouped = {
        "daily": [
            _browse_candidate("foo/bar", stars=1_234, language="Rust",
                              source="trending:daily", stars_today=56),
            _browse_candidate("baz/qux", stars=900, language="Go",
                              source="trending:daily", stars_today=12),
        ],
    }
    md = render_browse_markdown(DISCOVERED_AT, grouped, order=("daily",), min_stars=50)

    assert f"# Trending snapshot — {DISCOVERED_AT}" in md
    assert "min_stars floor: 50" in md
    assert "## Daily trending" in md
    # numbered list within the section
    assert "1. **foo/bar**" in md
    assert "2. **baz/qux**" in md
    # item line carries growth label, stars, language
    assert "56 stars today" in md
    assert "1,234★" in md
    assert "Rust" in md
    # url line
    assert "https://github.com/foo/bar" in md


def test_render_browse_markdown_empty_source_placeholder():
    grouped = {"daily": []}
    md = render_browse_markdown(DISCOVERED_AT, grouped, order=("daily",), min_stars=50)

    assert "## Daily trending" in md
    assert "_No repos right now._" in md


def test_render_browse_markdown_order_controls_section_order():
    grouped = {
        "daily": [_browse_candidate("d/aily", stars=100, language="Go", source="trending:daily")],
        "weekly": [_browse_candidate("w/eekly", stars=100, language="Go", source="trending:weekly")],
    }
    md = render_browse_markdown(DISCOVERED_AT, grouped, order=("weekly", "daily"), min_stars=50)

    assert md.index("## Weekly trending") < md.index("## Daily trending")
