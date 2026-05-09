"""Send a single file to Claude and get a structured review back."""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any

import anthropic

from .types import FileEntry, ReviewResult

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a research analyst reviewing newly declassified UAP \
(Unidentified Anomalous Phenomena) records released by the U.S. Department of War.

For each document, produce a faithful, source-grounded summary. Do not speculate \
beyond the text. Quote specific phrases when claims are notable. Flag redactions, \
missing pages, ambiguous handwriting, and any cross-references to other case files. \
Use neutral, evidence-first language — distinguish between what witnesses reported, \
what investigators concluded, and what is unverified."""

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Concise human-readable title"},
        "document_type": {
            "type": "string",
            "description": "e.g. memo, witness statement, photograph, technical report, sketch, news clipping",
        },
        "summary": {"type": "string", "description": "2-4 paragraph plain-text summary"},
        "incident_date": {"type": "string", "description": "Date of described event, or empty"},
        "incident_location": {"type": "string", "description": "Location, or empty"},
        "key_entities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "People, units, agencies, locations explicitly named",
        },
        "phenomenon_description": {
            "type": "string",
            "description": "What the witness/document describes (shape, behavior, duration, etc.)",
        },
        "key_claims": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-7 atomic factual claims made by the document",
        },
        "redactions_note": {
            "type": "string",
            "description": "Note any redactions, missing pages, or illegible content",
        },
        "cross_references": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Other case files, serial numbers, or documents referenced",
        },
        "notability": {
            "type": "string",
            "description": "Why this document is notable (or 'routine' if not)",
        },
    },
    "required": [
        "title",
        "document_type",
        "summary",
        "key_claims",
        "notability",
        "key_entities",
        "phenomenon_description",
        "incident_date",
        "incident_location",
        "redactions_note",
        "cross_references",
    ],
    "additionalProperties": False,
}


class Reviewer:
    def __init__(self, model: str = DEFAULT_MODEL, client: anthropic.Anthropic | None = None):
        self.model = model
        self.client = client or anthropic.Anthropic()

    def review(self, file_path: Path, entry: FileEntry | None = None) -> ReviewResult:
        """Send one local file to Claude. Returns a ReviewResult."""
        content = _build_content(file_path, entry)
        log.info("Reviewing %s (%d bytes) with %s", file_path.name, file_path.stat().st_size, self.model)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": REVIEW_SCHEMA}},
        )
        text = next(b.text for b in response.content if b.type == "text")
        import json
        data = json.loads(text)
        return ReviewResult(**data)


def _build_content(file_path: Path, entry: FileEntry | None) -> list[dict[str, Any]]:
    media_type, _ = mimetypes.guess_type(file_path.name)
    media_type = media_type or "application/octet-stream"
    raw = file_path.read_bytes()

    context = _format_context(entry) if entry else ""
    user_text = (
        f"{context}\nReview this declassified file. Extract structured analysis "
        "per the required schema. Be faithful to the source — do not invent facts."
    )

    if media_type == "application/pdf":
        b64 = base64.standard_b64encode(raw).decode()
        return [
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
            },
            {"type": "text", "text": user_text},
        ]
    if media_type.startswith("image/"):
        b64 = base64.standard_b64encode(raw).decode()
        return [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64},
            },
            {"type": "text", "text": user_text},
        ]
    text = raw.decode("utf-8", errors="replace")
    return [{"type": "text", "text": f"{user_text}\n\n--- FILE CONTENTS ---\n{text}"}]


def _format_context(entry: FileEntry) -> str:
    fields = [
        ("Asset name", entry.asset_name),
        ("Agency", entry.agency),
        ("Release date", entry.release_date),
        ("Incident date", entry.incident_date),
        ("Incident location", entry.incident_location),
        ("Site description", entry.description),
    ]
    lines = [f"- {label}: {value}" for label, value in fields if value]
    if not lines:
        return ""
    return "Page metadata for this file:\n" + "\n".join(lines) + "\n"
