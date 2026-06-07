from __future__ import annotations

from daily_tool_discovery.models import Candidate, CandidateDecision


def render_briefing(
    date: str,
    selected: list[tuple[Candidate, CandidateDecision]],
    filtered_count: int = 0,
) -> str:
    _validate_pairs(selected)
    try_items = [(c, d) for c, d in selected if d.action == "try"]
    save_items = [(c, d) for c, d in selected if d.action == "save"]
    review_items = [(c, d) for c, d in selected if d.action == "review"]
    explore_items = [(c, d) for c, d in selected if d.action == "explore"]
    ignore_items = [(c, d) for c, d in selected if d.action == "ignore"]

    lines = [f"# Daily Tool Discovery Briefing - {date}", ""]
    lines.extend(_render_section("Try Today", try_items, "No try-worthy item today.", include_trial=True))
    lines.extend(_render_section("Save", save_items, "No saved items today.", include_trial=False))
    lines.extend(_render_section("Review yourself", review_items, "No items need manual review today.", include_trial=False))
    lines.extend(_render_section("🎲 Explore", explore_items, "No exploration pick today.", include_trial=False))
    lines.extend(_render_section("Ignore", ignore_items, "No explicit ignores today.", include_trial=False))
    lines.append(f"Filtered {filtered_count} suspicious candidates.")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_section(title, items, empty, include_trial):
    lines = [f"## {title}", ""]
    if not items:
        lines.extend([empty, ""])
        return lines

    if title == "🎲 Explore":
        lines.append("_Outside your usual interests — included on purpose. Don't dismiss it just because it doesn't match your profile._")
        lines.append("")

    for candidate, decision in items:
        caveat = _inline_text(decision.caveat)
        lines.extend(
            [
                f"### {_inline_text(candidate.name)}",
                f"- Link: {_inline_text(candidate.url)}",
                f"- Type: {_inline_text(candidate.kind)}",
                f"- Score: {decision.score}",
                f"- Signals: {_metric_line(candidate)}",
                f"- Why it matters: {_inline_text(decision.reason)}",
            ]
        )
        if include_trial:
            lines.append("- 15-minute trial: Open the project page, inspect install steps, and decide whether to schedule an installation separately.")
        if caveat:
            lines.append(f"- Risk or caveat: {caveat}")
        flags = candidate.metadata.get("risk_flags") or []
        if flags:
            lines.append(f"- Risk flags: {', '.join(str(f) for f in flags)}")
        lines.append("")
    return lines


def _metric_line(candidate: Candidate) -> str:
    md = candidate.metadata
    stars = md.get("stars", 0)
    forks = md.get("forks", 0)
    issues = md.get("open_issues", 0)
    pushed = md.get("pushed_at") or "unknown"
    owner = md.get("owner_login") or "unknown"
    owner_type = md.get("owner_type") or "?"
    return f"{stars}★ · {forks} forks · {issues} issues/PRs · updated {pushed} · by {owner} ({owner_type})"


def _validate_pairs(selected):
    for candidate, decision in selected:
        if candidate.id != decision.candidate_id:
            raise ValueError(
                f"decision candidate_id {decision.candidate_id!r} does not match candidate id {candidate.id!r}"
            )


def _inline_text(value: object) -> str:
    return " ".join(str(value).split())
