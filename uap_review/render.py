"""Render review results to markdown for humans."""

from __future__ import annotations

from .types import FileEntry, ReviewResult


def render_review(entry: FileEntry, review: ReviewResult) -> str:
    lines: list[str] = []
    lines.append(f"# {review.title}")
    lines.append("")
    lines.append(f"- **Asset name:** {entry.asset_name}")
    lines.append(f"- **Document type:** {review.document_type}")
    if entry.agency:
        lines.append(f"- **Agency:** {entry.agency}")
    if review.incident_date or entry.incident_date:
        lines.append(f"- **Incident date:** {review.incident_date or entry.incident_date}")
    if review.incident_location or entry.incident_location:
        lines.append(f"- **Incident location:** {review.incident_location or entry.incident_location}")
    if entry.release_date:
        lines.append(f"- **Release date:** {entry.release_date}")
    if entry.download_url:
        lines.append(f"- **Source:** [{entry.download_url}]({entry.download_url})")
    lines.append("")
    lines.append("## Summary")
    lines.append(review.summary)
    lines.append("")
    if review.phenomenon_description:
        lines.append("## Phenomenon described")
        lines.append(review.phenomenon_description)
        lines.append("")
    if review.key_claims:
        lines.append("## Key claims")
        for c in review.key_claims:
            lines.append(f"- {c}")
        lines.append("")
    if review.key_entities:
        lines.append("## Entities named")
        lines.append(", ".join(review.key_entities))
        lines.append("")
    if review.cross_references:
        lines.append("## Cross-references")
        for ref in review.cross_references:
            lines.append(f"- {ref}")
        lines.append("")
    if review.redactions_note:
        lines.append("## Redactions / gaps")
        lines.append(review.redactions_note)
        lines.append("")
    lines.append("## Notability")
    lines.append(review.notability)
    lines.append("")
    return "\n".join(lines)


def render_release_digest(release_label: str, items: list[tuple[FileEntry, ReviewResult]]) -> str:
    lines = [f"# {release_label} — digest", "", f"_{len(items)} files reviewed_", ""]
    for entry, review in items:
        lines.append(f"## {review.title}")
        lines.append(f"_{review.document_type} — {entry.asset_name}_")
        lines.append("")
        lines.append(review.summary.split("\n\n")[0])
        lines.append("")
    return "\n".join(lines)
