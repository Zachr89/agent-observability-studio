"""Track which files we've already reviewed so we don't reprocess them.

State lives in a single JSON file: stable_id -> processing record.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Record:
    stable_id: str
    asset_name: str
    download_url: str
    sha256: str = ""
    summary_md_path: str = ""
    summary_json_path: str = ""
    reviewed_at: float = field(default_factory=time.time)
    error: str = ""


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists() and self.path.stat().st_size > 0:
            self._data = json.loads(self.path.read_text())
        else:
            self._data = {}

    def has(self, stable_id: str) -> bool:
        rec = self._data.get(stable_id)
        return bool(rec) and not rec.get("error")

    def record(self, rec: Record) -> None:
        self._data[rec.stable_id] = asdict(rec)
        self._flush()

    def get(self, stable_id: str) -> dict | None:
        return self._data.get(stable_id)

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True))
        tmp.replace(self.path)
