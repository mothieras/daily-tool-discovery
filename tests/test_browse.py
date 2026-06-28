"""Tests for the ``browse`` CLI subcommand (cli.run_browse).

``run_browse`` is read-only: it scrapes/searches GitHub Trending and renders
raw Markdown, writing no state. All GitHub access is faked here — daily/weekly
via a patched ``UrllibTextTransport`` and new/fast-growing via a recording
fake client returned from a patched ``_make_github_client``.
"""

import re

import pytest

from daily_tool_discovery import cli, trending
from daily_tool_discovery.models import Candidate

DATE = "2026-06-28"


# --- fakes / fixtures -------------------------------------------------------


class FakeTextTransport:
    def __init__(self, html):
        self.html = html

    def get_text(self, url):
        return self.html


class RecordingGitHubClient:
    def __init__(self, search_results=None):
        self.search_results = search_results or []
        self.search_calls = []

    def search_repositories(self, query, discovered_at, kind, per_page=10,
                            min_stars=0, sort="updated", order="desc"):
        self.search_calls.append({"query": query, "kind": kind, "per_page": per_page,
                                  "min_stars": min_stars, "sort": sort, "order": order})
        return [
            Candidate(
                id=f"github:{name}", name=name, url=f"https://github.com/{name}",
                source="github", summary="", tags=[], kind=kind,
                discovered_at=discovered_at, metadata={"stars": 321, "language": "Go"},
            )
            for name in self.search_results
        ]


def _article(full_name, stars):
    owner, repo = full_name.split("/")
    return (
        '<article class="Box-row">'
        f'<h2 class="h3"><a href="/{full_name}">{owner} / {repo}</a></h2>'
        f'<a href="/{full_name}/stargazers"><svg height="16" width="16"></svg> {stars:,} </a>'
        '<span itemprop="programmingLanguage">Python</span>'
        "</article>"
    )


def _page(*articles):
    return '<div class="Box">' + "".join(articles) + "</div>"


def _patch_transport(monkeypatch, html):
    """Make gather_trending's default UrllibTextTransport() return canned HTML."""
    monkeypatch.setattr(trending, "UrllibTextTransport", lambda: FakeTextTransport(html))


def _patch_client(monkeypatch, client):
    monkeypatch.setattr(cli, "_make_github_client", lambda: client)


def _write_profile(root, min_stars):
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "profile.toml").write_text(
        f'[meta]\nname = "t"\n[trust]\nmin_stars = {min_stars}\n', encoding="utf-8"
    )


def _numbered_items(md):
    return [ln for ln in md.splitlines() if re.match(r"\d+\. \*\*", ln)]


# --- tests ------------------------------------------------------------------


def test_browse_daily_returns_one_section_capped_at_limit(tmp_path, monkeypatch, capsys):
    html = _page(*[_article(f"owner/repo{i}", 200 + i) for i in range(8)])
    _patch_transport(monkeypatch, html)
    _patch_client(monkeypatch, RecordingGitHubClient())

    md = cli.run_browse(root=tmp_path, source="daily", limit=5, date=DATE)
    capsys.readouterr()  # swallow the printed snapshot

    assert "## Daily trending" in md
    # only the daily section is rendered
    assert "## Weekly trending" not in md
    assert "## New repos" not in md
    assert len(_numbered_items(md)) == 5  # 8 scraped, capped to limit


def test_browse_missing_token_raises_token_error(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # _make_github_client is NOT patched here: the real one must raise.
    with pytest.raises(cli.TokenError):
        cli.run_browse(root=tmp_path, source="daily", date=DATE)


def test_browse_new_uses_search_pathway_with_7d_lookback(tmp_path, monkeypatch, capsys):
    client = RecordingGitHubClient(search_results=["new/repo"])
    _patch_client(monkeypatch, client)

    cli.run_browse(root=tmp_path, source="new", since="7d", date=DATE)
    capsys.readouterr()

    assert len(client.search_calls) == 1
    # 7 days before 2026-06-28 -> 2026-06-21, via the `created:>` (new) pathway
    assert client.search_calls[0]["query"] == "created:>2026-06-21"
    assert client.search_calls[0]["kind"] == "trending-new"


def test_browse_honors_profile_min_stars_without_override(tmp_path, monkeypatch, capsys):
    _write_profile(tmp_path, min_stars=77)
    html = _page(_article("lo/repo", 60), _article("hi/repo", 100))
    _patch_transport(monkeypatch, html)
    _patch_client(monkeypatch, RecordingGitHubClient())

    md = cli.run_browse(root=tmp_path, source="daily", date=DATE)  # no min_stars override
    capsys.readouterr()

    assert "min_stars floor: 77" in md
    assert "hi/repo" in md       # 100 >= 77 -> kept
    assert "lo/repo" not in md   # 60 < 77  -> floored out


def test_browse_is_read_only(tmp_path, monkeypatch, capsys):
    html = _page(_article("owner/repo", 200))
    _patch_transport(monkeypatch, html)
    _patch_client(monkeypatch, RecordingGitHubClient())

    cli.run_browse(root=tmp_path, source="daily", date=DATE)
    capsys.readouterr()

    # browse writes no briefing, history, or candidate state
    assert not (tmp_path / "briefings").exists()
    assert not (tmp_path / "history.jsonl").exists()
    assert not (tmp_path / "candidates").exists()
    # nothing at all is written under root
    assert sorted(p.name for p in tmp_path.iterdir()) == []
