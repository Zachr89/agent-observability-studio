# uap_review

Scrape the U.S. Department of War's UAP file release page (`https://www.war.gov/UFO/`) and produce a Claude-generated summary of every declassified document, with state tracking so re-runs only process new files.

## Why Playwright

`war.gov/UFO/` is a JavaScript-rendered SPA behind Akamai bot protection. A plain `requests` GET returns 403 from anywhere outside a residential browser, and the file list isn't in the raw HTML. Playwright drives a real Chromium so the page actually renders, the file cards exist in the DOM, and downloads carry the correct TLS fingerprint and cookies.

## Setup

```bash
pip install -r uap_review/requirements.txt
playwright install chromium
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
# One-shot: scrape every page, download new files, summarize them.
python -m uap_review run

# Limit while testing.
python -m uap_review run --max-pages 1 --limit 3

# Watch the page; re-check every 6 hours.
python -m uap_review watch --interval-hours 6

# Review a single local file (skip the scraper entirely).
python -m uap_review review path/to/document.pdf

# Debug a scraper change by watching the browser.
python -m uap_review run --show-browser -v --max-pages 1
```

## Output layout

```
uap_output/
├── state.json                       # stable_id -> processing record (dedup)
├── Release_01/
│   ├── _digest.md                   # rollup of every reviewed file in the release
│   ├── raw/                         # downloaded source PDFs / images
│   ├── 65_HS1-834228961_..._SECTION_10.md
│   ├── 65_HS1-834228961_..._SECTION_10.json
│   └── ...
```

Each `.md` is a human-readable analyst report. Each `.json` carries the same fields (title, document type, summary, key claims, entities, redactions, cross-references, notability) plus the source file's SHA-256.

## Knobs

- `--model` — defaults to `claude-sonnet-4-6`. Use `claude-opus-4-7` for deeper analysis on tricky documents, `claude-haiku-4-5` for cheap bulk triage.
- `--max-pages` — bounds the scraper. Useful to test before running across all 17 pages.
- `--limit` — bounds the reviewer. Independent of scraper limit.
- `--show-browser` — non-headless Chromium so you can watch the scrape and update selectors if the site's markup drifts.
- `-v` — verbose logging.

## When the page changes

The scraper uses defensive CSS selectors (`scraper.py:DEFAULTS`). If war.gov ships a redesign and the cards no longer match, run with `--show-browser -v`, watch which selectors miss, then update `DEFAULTS`. The detail-panel scraping uses regex-on-text rather than DOM structure so labels can move without breaking it.

## Cost note

A typical FBI PDF is 1-50 pages. Sonnet 4.6 review cost runs roughly $0.005 - $0.05 per file depending on length. Release 01 looked like ~17 pages × ~5-8 cards = ~100 documents, so plan for $5-$50 on a full pass with Sonnet (10× that on Opus).
