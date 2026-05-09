"""Download a file URL to disk, reusing browser context to bypass Akamai."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def safe_filename(name: str, fallback: str = "file") -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or fallback


def download(context: Any, url: str, dest: Path) -> tuple[Path, str]:
    """Download `url` using a Playwright BrowserContext (carries the right cookies/TLS).

    Returns (path, sha256).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %s -> %s", url, dest)
    response = context.request.get(url, timeout=120_000)
    if response.status >= 400:
        raise RuntimeError(f"GET {url} returned {response.status}")
    body = response.body()
    dest.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    log.info("  %d bytes, sha256=%s", len(body), digest[:12])
    return dest, digest
