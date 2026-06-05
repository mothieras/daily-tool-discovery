from __future__ import annotations

from daily_tool_discovery.models import Candidate, CandidateDecision


def render_briefing(date: str, selected: list[tuple[Candidate, CandidateDecision]]) -> str:
    _validate_pairs(selected)
    try_items = [(c, d) for c, d in selected if d.action == "try"]
    save_items = [(c, d) for c, d in selected if d.action == "save"]
    ignore_items = [(c, d) for c, d in selected if d.action == "ignore"]

    lines = [f"# Daily Tool Discovery Briefing - {date}", ""]
    lines.extend(_render_section("Try Today", try_items, empty="No try-worthy item today.", include_trial=True))
    lines.extend(_render_section("Save", save_items, empty="No saved items today.", include_trial=False))
    lines.extend(_render_section("Ignore", ignore_items, empty="No explicit ignores today.", include_trial=False))
    return "\n".join(lines).rstrip() + "\n"


def _render_section(
    title: str,
    items: list[tuple[Candidate, CandidateDecision]],
    empty: str,
    include_trial: bool,
) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.extend([empty, ""])
        return lines

    for candidate, decision in items:
        caveat = _inline_text(decision.caveat)
        lines.extend(
            [
                f"### {_inline_text(candidate.name)}",
                f"- Link: {_inline_text(candidate.url)}",
                f"- Type: {_inline_text(candidate.kind)}",
                f"- Score: {decision.score}",
                f"- Why it matters: {_inline_text(decision.reason)}",
            ]
        )
        if include_trial:
            lines.append("- 15-minute trial: Open the project page, inspect install steps, and decide whether to schedule an installation separately.")
        if caveat:
            lines.append(f"- Risk or caveat: {caveat}")
        lines.append("")

    return lines


def _validate_pairs(selected: list[tuple[Candidate, CandidateDecision]]) -> None:
    for candidate, decision in selected:
        if candidate.id != decision.candidate_id:
            raise ValueError(
                f"decision candidate_id {decision.candidate_id!r} does not match candidate id {candidate.id!r}"
            )


def _inline_text(value: object) -> str:
    return " ".join(str(value).split())
