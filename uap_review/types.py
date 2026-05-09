"""Data models shared across modules."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class FileEntry:
    """One downloadable asset listed on the war.gov/UFO page."""

    asset_name: str
    download_url: str
    file_type: str = ""
    agency: str = ""
    release_date: str = ""
    incident_date: str = ""
    incident_location: str = ""
    description: str = ""
    release_label: str = "Release 01"

    def stable_id(self) -> str:
        """Stable identifier for dedup. Prefer the download URL; fall back to asset name."""
        return self.download_url or self.asset_name

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewResult:
    """Structured analysis returned by Claude for one file."""

    title: str
    document_type: str
    summary: str
    key_claims: list[str]
    notability: str
    incident_date: str = ""
    incident_location: str = ""
    key_entities: list[str] = field(default_factory=list)
    phenomenon_description: str = ""
    redactions_note: str = ""
    cross_references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
