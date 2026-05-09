"""Command-line entry: run, watch, review."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from .downloader import download, safe_filename
from .render import render_release_digest, render_review
from .reviewer import DEFAULT_MODEL, Reviewer
from .scraper import scrape
from .state import Record, StateStore
from .types import FileEntry, ReviewResult


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_run(args: argparse.Namespace) -> int:
    _setup_logging(args.verbose)
    output_dir = Path(args.output_dir)
    state = StateStore(Path(args.state_file))
    reviewer = Reviewer(model=args.model)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.show_browser)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 1800},
        )
        try:
            entries = _scrape_with_context(context, args)
            _review_entries(entries, context, state, reviewer, output_dir, limit=args.limit)
        finally:
            context.close()
            browser.close()
    return 0


def _scrape_with_context(context, args: argparse.Namespace) -> list[FileEntry]:
    """Scrape using an existing Playwright context (so we can reuse it for downloads)."""
    from .scraper import DEFAULTS, _click_next, _scrape_current_page

    page = context.new_page()
    page.goto("https://www.war.gov/UFO/", wait_until="networkidle", timeout=60_000)
    try:
        page.wait_for_selector(DEFAULTS["wait_for"], timeout=30_000)
    except Exception:
        logging.warning("Initial wait_for did not appear; continuing")

    entries: list[FileEntry] = []
    seen: set[str] = set()
    page_num = 0
    while True:
        page_num += 1
        logging.info("Scraping page %d", page_num)
        page_entries = _scrape_current_page(page, DEFAULTS)
        for e in page_entries:
            if e.stable_id() not in seen:
                seen.add(e.stable_id())
                entries.append(e)
        if args.max_pages and page_num >= args.max_pages:
            break
        if not _click_next(page, DEFAULTS):
            break
    page.close()
    logging.info("Scraped %d entries across %d page(s)", len(entries), page_num)
    return entries


def _review_entries(
    entries: list[FileEntry],
    context,
    state: StateStore,
    reviewer: Reviewer,
    output_dir: Path,
    limit: int | None = None,
) -> None:
    pending = [e for e in entries if not state.has(e.stable_id())]
    if limit:
        pending = pending[:limit]
    logging.info("%d new entries to review (skipping %d already done)",
                 len(pending), len(entries) - len(pending))

    by_release: dict[str, list[tuple[FileEntry, ReviewResult]]] = {}
    for entry in pending:
        try:
            result = _process_one(entry, context, reviewer, output_dir, state)
            if result:
                by_release.setdefault(entry.release_label, []).append((entry, result))
        except Exception as exc:
            logging.exception("Failed to process %s", entry.asset_name)
            state.record(Record(
                stable_id=entry.stable_id(),
                asset_name=entry.asset_name,
                download_url=entry.download_url,
                error=str(exc),
            ))

    for release_label, items in by_release.items():
        digest_dir = output_dir / safe_filename(release_label)
        digest_dir.mkdir(parents=True, exist_ok=True)
        digest = render_release_digest(release_label, items)
        (digest_dir / "_digest.md").write_text(digest)
        logging.info("Wrote digest: %s", digest_dir / "_digest.md")


def _process_one(
    entry: FileEntry,
    context,
    reviewer: Reviewer,
    output_dir: Path,
    state: StateStore,
) -> ReviewResult | None:
    if not entry.download_url:
        logging.warning("Skipping %s: no download URL", entry.asset_name)
        return None

    release_dir = output_dir / safe_filename(entry.release_label)
    raw_dir = release_dir / "raw"
    base = safe_filename(entry.asset_name)

    suffix = Path(entry.download_url.split("?", 1)[0]).suffix or ".bin"
    file_path = raw_dir / f"{base}{suffix}"
    file_path, digest = download(context, entry.download_url, file_path)

    review = reviewer.review(file_path, entry)

    md = render_review(entry, review)
    md_path = release_dir / f"{base}.md"
    json_path = release_dir / f"{base}.json"
    md_path.write_text(md)
    import json as _json
    json_path.write_text(_json.dumps(
        {"entry": entry.to_dict(), "review": review.to_dict(), "sha256": digest},
        indent=2,
    ))
    state.record(Record(
        stable_id=entry.stable_id(),
        asset_name=entry.asset_name,
        download_url=entry.download_url,
        sha256=digest,
        summary_md_path=str(md_path),
        summary_json_path=str(json_path),
    ))
    logging.info("Reviewed %s -> %s", entry.asset_name, md_path)
    return review


def cmd_watch(args: argparse.Namespace) -> int:
    """Re-run `cmd_run` on an interval until interrupted."""
    interval = args.interval_hours * 3600
    while True:
        try:
            cmd_run(args)
        except KeyboardInterrupt:
            return 0
        except Exception:
            logging.exception("Run failed; will retry next cycle")
        logging.info("Sleeping %.1f hours", args.interval_hours)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            return 0


def cmd_review(args: argparse.Namespace) -> int:
    """Review a local file directly (no scraping)."""
    _setup_logging(args.verbose)
    reviewer = Reviewer(model=args.model)
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 1
    review = reviewer.review(file_path)
    entry = FileEntry(asset_name=file_path.name, download_url=str(file_path))
    print(render_review(entry, review))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="uap-review",
        description="Scrape war.gov/UFO/ and summarize each declassified file via Claude.",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-dir", default="./uap_output", help="Where to write summaries")
    common.add_argument("--state-file", default="./uap_output/state.json")
    common.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default: {DEFAULT_MODEL})")
    common.add_argument("--max-pages", type=int, default=None, help="Stop after N pages of cards")
    common.add_argument("--limit", type=int, default=None, help="Review at most N new files")
    common.add_argument("--show-browser", action="store_true", help="Run Chromium non-headless (debugging)")

    p_run = sub.add_parser("run", parents=[common], help="One-shot scrape + review")
    p_run.set_defaults(func=cmd_run, verbose=False)

    p_watch = sub.add_parser("watch", parents=[common], help="Poll the page on an interval")
    p_watch.add_argument("--interval-hours", type=float, default=6.0)
    p_watch.set_defaults(func=cmd_watch, verbose=False)

    p_review = sub.add_parser("review", help="Review one local file ad-hoc")
    p_review.add_argument("file", help="Path to PDF, image, or text file")
    p_review.add_argument("--model", default=DEFAULT_MODEL)
    p_review.set_defaults(func=cmd_review, verbose=False)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.verbose = getattr(args, "verbose", False) or False
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
