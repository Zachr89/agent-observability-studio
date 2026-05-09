"""Scrape war.gov/UFO/ for downloadable UAP file metadata.

The page is a JS-rendered SPA behind Akamai bot protection, so we use a real
headless Chromium via Playwright. Selectors are written defensively because we
can't validate them from a sandbox — log everything and let the operator tune.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .types import FileEntry

log = logging.getLogger(__name__)

UFO_URL = "https://www.war.gov/UFO/"

# Default selectors. If the markup drifts, override via CLI / env.
DEFAULTS = {
    "card": "[class*='card'], [class*='Card'], [class*='item'], [class*='tile']",
    "next_button": "button:has-text('NEXT'), a:has-text('NEXT')",
    "download_link": "a:has-text('DOWNLOAD'), button:has-text('DOWNLOAD'), a[href*='.pdf']",
    "close_detail": "button:has-text('X'), button[aria-label='Close']",
    "wait_for": "text=AGENCY",
}


@contextmanager
def _browser(headless: bool = True, debug_dir: Path | None = None):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 1800},
        )
        page = context.new_page()
        try:
            yield page, context
        finally:
            if debug_dir is not None:
                debug_dir.mkdir(parents=True, exist_ok=True)
                try:
                    page.screenshot(path=str(debug_dir / "final.png"), full_page=True)
                    (debug_dir / "final.html").write_text(page.content())
                except Exception:
                    log.exception("Failed to write debug artifacts")
            context.close()
            browser.close()


def scrape(
    *,
    headless: bool = True,
    max_pages: int | None = None,
    selectors: dict[str, str] | None = None,
    debug_dir: Path | None = None,
) -> list[FileEntry]:
    """Walk every page of file cards, return one FileEntry per asset."""
    sel = {**DEFAULTS, **(selectors or {})}
    entries: list[FileEntry] = []
    seen_ids: set[str] = set()

    with _browser(headless=headless, debug_dir=debug_dir) as (page, _ctx):
        log.info("Loading %s", UFO_URL)
        page.goto(UFO_URL, wait_until="networkidle", timeout=60_000)
        try:
            page.wait_for_selector(sel["wait_for"], timeout=30_000)
        except Exception:
            log.warning("Initial wait_for selector did not appear; continuing anyway")

        page_num = 0
        while True:
            page_num += 1
            log.info("Scraping page %d", page_num)
            page_entries = _scrape_current_page(page, sel)
            new = [e for e in page_entries if e.stable_id() not in seen_ids]
            for e in new:
                seen_ids.add(e.stable_id())
                entries.append(e)
            log.info("  found %d entries (%d new)", len(page_entries), len(new))

            if max_pages and page_num >= max_pages:
                break
            if not _click_next(page, sel):
                log.info("No more pages")
                break

    log.info("Scrape complete: %d total entries", len(entries))
    return entries


def _scrape_current_page(page: Any, sel: dict[str, str]) -> list[FileEntry]:
    """Iterate cards on the current page and harvest each detail panel."""
    cards = page.query_selector_all(sel["card"])
    log.debug("  card selector matched %d nodes", len(cards))

    # Some cards on the page are nav/UI chrome. Filter to ones whose text mentions a known field.
    file_cards = [c for c in cards if _looks_like_file_card(c)]
    log.debug("  %d cards look like file entries", len(file_cards))

    entries: list[FileEntry] = []
    for idx, card in enumerate(file_cards):
        try:
            entry = _open_and_extract(page, card, sel)
            if entry:
                entries.append(entry)
        except Exception:
            log.exception("  card %d failed", idx)
    return entries


def _looks_like_file_card(card: Any) -> bool:
    try:
        text = (card.inner_text() or "").upper()
    except Exception:
        return False
    return "AGENCY" in text and "TYPE" in text


def _open_and_extract(page: Any, card: Any, sel: dict[str, str]) -> FileEntry | None:
    """Click a card, scrape its detail view, then close it."""
    asset_name = _first_line(card.inner_text() or "")
    card.scroll_into_view_if_needed()
    card.click()
    try:
        page.wait_for_selector(sel["download_link"], timeout=10_000)
    except Exception:
        log.debug("    download link did not appear for %s", asset_name)

    detail_text = page.inner_text("body") or ""
    download_url = _extract_download_url(page, sel)

    entry = FileEntry(
        asset_name=asset_name,
        download_url=download_url,
        file_type=_extract_field(detail_text, "TYPE"),
        agency=_extract_field(detail_text, "AGENCY"),
        release_date=_extract_field(detail_text, "RELEASE DATE"),
        incident_date=_extract_field(detail_text, "INCIDENT DATE"),
        incident_location=_extract_field(detail_text, "INCIDENT LOCATION"),
        description=_extract_description(detail_text),
    )

    _try_click(page, sel["close_detail"])
    return entry


def _extract_download_url(page: Any, sel: dict[str, str]) -> str:
    for s in sel["download_link"].split(", "):
        try:
            for link in page.query_selector_all(s):
                href = link.get_attribute("href")
                if href:
                    return href
        except Exception:
            continue
    return ""


def _extract_field(text: str, label: str) -> str:
    """Pull a labeled value like 'AGENCY [FBI]' or 'AGENCY\\nFBI' out of detail text."""
    pattern = rf"{re.escape(label)}\s*[:\-]?\s*\[?([^\[\]\n]+?)\]?(?:\n|$)"
    m = re.search(pattern, text)
    return m.group(1).strip() if m else ""


def _extract_description(text: str) -> str:
    """Best-effort: grab the paragraph before the DOWNLOAD button."""
    m = re.search(r"(.{50,2000}?)\s*[>›]?\s*DOWNLOAD", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _first_line(text: str) -> str:
    return text.strip().split("\n", 1)[0].strip()


def _click_next(page: Any, sel: dict[str, str]) -> bool:
    btn = page.query_selector(sel["next_button"])
    if not btn:
        return False
    try:
        if btn.is_disabled():
            return False
    except Exception:
        pass
    try:
        btn.scroll_into_view_if_needed()
        btn.click()
        page.wait_for_load_state("networkidle", timeout=30_000)
        return True
    except Exception:
        log.exception("Failed to click NEXT")
        return False


def _try_click(page: Any, selector: str) -> None:
    for s in selector.split(", "):
        el = page.query_selector(s)
        if el:
            try:
                el.click()
                return
            except Exception:
                continue
