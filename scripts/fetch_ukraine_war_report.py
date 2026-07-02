#!/usr/bin/env python3
"""
fetch_ukraine_war_report.py
----------------------------
Searches for Russia-Ukraine War developments across three time ranges,
deduplicates results, and writes a structured .docx report.

Environment variables:
  SERPAPI_KEY          — SerpAPI key (primary)
  BING_SEARCH_API_KEY  — Bing Search API key (fallback)

Usage:
  python scripts/fetch_ukraine_war_report.py
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
import time
import warnings
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

# ---------------------------------------------------------------------------
# Optional heavy dependencies — graceful degradation if absent
# ---------------------------------------------------------------------------
try:
    import requests
except ImportError:
    sys.exit(
        "ERROR: 'requests' is required.  Install via: pip install requests"
    )

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    warnings.warn(
        "python-docx not installed — document will NOT be generated.\n"
        "Install via: pip install python-docx",
        stacklevel=1,
    )

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TODAY_ISO = date.today().isoformat()                         # YYYY-MM-DD
OUTPUT_FILENAME = f"russia_ukraine_war_{TODAY_ISO}.docx"

RESULTS_PER_QUERY = 10          # minimum per-query result count
SIMILARITY_THRESHOLD = 0.85     # cosine similarity cut-off for dedup
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0        # seconds

SEARCH_QUERIES: list[dict[str, Any]] = [
    # ── Historical / origins ───────────────────────────────────────────────
    {
        "q": "Russia Ukraine conflict history pre-2022",
        "time_range": "historical",
        "tbs": "cdr:1,cd_min:1/1/2000,cd_max:12/31/2021",
    },
    {
        "q": "Crimea annexation 2014 Russia Ukraine",
        "time_range": "historical",
        "tbs": "cdr:1,cd_min:1/1/2013,cd_max:12/31/2015",
    },
    {
        "q": "Donbas conflict origins separatists Ukraine",
        "time_range": "historical",
        "tbs": "cdr:1,cd_min:1/1/2014,cd_max:12/31/2021",
    },
    # ── 2022 invasion ──────────────────────────────────────────────────────
    {
        "q": "Russia Ukraine invasion February 2022",
        "time_range": "2022_invasion",
        "tbs": "cdr:1,cd_min:2/1/2022,cd_max:5/31/2022",
    },
    {
        "q": "Kyiv offensive 2022 Russian forces retreat",
        "time_range": "2022_invasion",
        "tbs": "cdr:1,cd_min:2/1/2022,cd_max:12/31/2022",
    },
    {
        "q": "Ukraine war 2022 timeline battles Mariupol",
        "time_range": "2022_invasion",
        "tbs": "cdr:1,cd_min:2/1/2022,cd_max:12/31/2022",
    },
    # ── Recent / ongoing ───────────────────────────────────────────────────
    {
        "q": "Russia Ukraine war latest news 2024",
        "time_range": "recent",
        "tbs": "cdr:1,cd_min:1/1/2024,cd_max:12/31/2024",
    },
    {
        "q": "Ukraine frontline update 2025 Zaporizhzhia Kherson",
        "time_range": "recent",
        "tbs": "cdr:1,cd_min:1/1/2025,cd_max:12/31/2025",
    },
    {
        "q": "Russia Ukraine ceasefire negotiations peace talks 2025",
        "time_range": "recent",
        "tbs": "cdr:1,cd_min:1/1/2025,cd_max:12/31/2025",
    },
]

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _with_retries(fn, *args, **kwargs):
    """Call fn(*args, **kwargs) with exponential back-off on transient errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except requests.exceptions.RequestException as exc:
            if attempt == MAX_RETRIES:
                log.warning("All %d retries exhausted: %s", MAX_RETRIES, exc)
                return None
            wait = RETRY_BACKOFF_BASE ** attempt
            log.warning(
                "Request failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt, MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)
    return None


def search_serpapi(query: str, api_key: str, num: int = RESULTS_PER_QUERY,
                   tbs: str = "") -> list[dict]:
    """Fetch organic results from SerpAPI."""
    params: dict[str, Any] = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num,
        "hl": "en",
        "gl": "us",
        "safe": "off",
    }
    if tbs:
        params["tbs"] = tbs

    url = "https://serpapi.com/search?" + urlencode(params)
    log.info("SerpAPI → %s", query)

    resp = _with_retries(requests.get, url, timeout=20)
    if resp is None:
        return []
    if not resp.ok:
        log.warning("SerpAPI HTTP %s for query: %s", resp.status_code, query)
        return []

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        log.warning("SerpAPI JSON decode error: %s", exc)
        return []

    return data.get("organic_results", [])


def search_bing(query: str, api_key: str, count: int = RESULTS_PER_QUERY,
                freshness: str = "") -> list[dict]:
    """Fetch results from Bing Web Search API v7."""
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    params: dict[str, Any] = {
        "q": query,
        "count": count,
        "mkt": "en-US",
        "safeSearch": "Off",
    }
    if freshness:
        params["freshness"] = freshness

    url = "https://api.bing.microsoft.com/v7.0/search?" + urlencode(params)
    log.info("Bing → %s", query)

    resp = _with_retries(requests.get, url, headers=headers, timeout=20)
    if resp is None:
        return []
    if not resp.ok:
        log.warning("Bing HTTP %s for query: %s", resp.status_code, query)
        return []

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        log.warning("Bing JSON decode error: %s", exc)
        return []

    return data.get("webPages", {}).get("value", [])


# ---------------------------------------------------------------------------
# Result normalisation
# ---------------------------------------------------------------------------

def _normalise_serpapi(raw: dict, time_range: str) -> Optional[dict]:
    url = raw.get("link", "").strip()
    title = raw.get("title", "").strip()
    snippet = (raw.get("snippet") or raw.get("rich_snippet", {}).get("top", {}).get("detected_extensions", {}).get("text", "") or "").strip()
    date_raw = raw.get("date", "") or ""

    if not url or not title:
        return None

    ts = _parse_timestamp(date_raw)
    return {
        "title": title,
        "source_url": url,
        "publication_timestamp": ts,
        "summary": _build_summary(title, snippet),
        "time_period_label": _period_label(ts, time_range),
        "is_new_finding": True,   # resolved later in dedup pass
        "_raw_snippet": snippet,
    }


def _normalise_bing(raw: dict, time_range: str) -> Optional[dict]:
    url = raw.get("url", "").strip()
    title = raw.get("name", "").strip()
    snippet = (raw.get("snippet") or "").strip()
    date_raw = raw.get("datePublished") or raw.get("dateLastCrawled") or ""

    if not url or not title:
        return None

    ts = _parse_timestamp(date_raw)
    return {
        "title": title,
        "source_url": url,
        "publication_timestamp": ts,
        "summary": _build_summary(title, snippet),
        "time_period_label": _period_label(ts, time_range),
        "is_new_finding": True,
        "_raw_snippet": snippet,
    }


def _parse_timestamp(raw: str) -> Optional[str]:
    """Return ISO 8601 timestamp or None."""
    if not raw:
        return None
    raw = raw.strip()
    # Already ISO-like
    iso_match = re.match(
        r"(\d{4}-\d{2}-\d{2})[T ]?(\d{2}:\d{2}:\d{2})?", raw
    )
    if iso_match:
        date_part = iso_match.group(1)
        time_part = iso_match.group(2) or "00:00:00"
        return f"{date_part}T{time_part}Z"
    # "Month DD, YYYY" or "DD Month YYYY"
    for fmt in ("%B %d, %Y", "%d %B %Y", "%b %d, %Y", "%d %b %Y",
                "%Y/%m/%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%dT00:00:00Z")
        except ValueError:
            continue
    return None


def _build_summary(title: str, snippet: str) -> str:
    """Combine title + snippet into a 2-4 sentence summary."""
    text = snippet.strip()
    if not text:
        text = title
    # Normalise whitespace
    text = re.sub(r"\s+", " ", text)
    # Split into rough sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    # Aim for 2-4 sentences; truncate or pad minimally
    if len(sentences) > 4:
        sentences = sentences[:4]
    if not sentences:
        return text[:500]
    return " ".join(sentences)


def _period_label(ts: Optional[str], time_range: str) -> str:
    """Human-readable period label derived from timestamp."""
    if ts:
        try:
            dt = datetime.strptime(ts[:10], "%Y-%m-%d")
            month_name = dt.strftime("%B %Y")
            return month_name
        except ValueError:
            pass
    # Fall back to range label
    return {
        "historical": "Pre-2022",
        "2022_invasion": "2022 Invasion",
        "recent": "2024–2025",
    }.get(time_range, "Unknown")


# ---------------------------------------------------------------------------
# TF-IDF cosine similarity (no numpy required)
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z]{3,}", text.lower())


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(tokens)
    total = sum(tf.values()) or 1
    return {t: (count / total) * idf.get(t, 0.0) for t, count in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _build_idf(corpus: list[list[str]]) -> dict[str, float]:
    N = len(corpus) or 1
    df: Counter = Counter()
    for doc in corpus:
        for term in set(doc):
            df[term] += 1
    return {t: math.log(N / (1 + n)) for t, n in df.items()}


def semantic_dedup(
    entries: list[dict], threshold: float = SIMILARITY_THRESHOLD
) -> list[dict]:
    """Remove entries whose summary is too similar to an already-accepted one."""
    tokenised = [_tokenise(e["summary"]) for e in entries]
    idf = _build_idf(tokenised)

    accepted: list[dict] = []
    accepted_vecs: list[dict[str, float]] = []

    for entry, tokens in zip(entries, tokenised):
        vec = _tfidf_vector(tokens, idf)
        too_similar = any(
            _cosine(vec, av) >= threshold for av in accepted_vecs
        )
        if too_similar:
            log.debug("Semantic dup dropped: %s", entry["source_url"])
            continue
        accepted.append(entry)
        accepted_vecs.append(vec)

    return accepted


# ---------------------------------------------------------------------------
# Deduplication pipeline
# ---------------------------------------------------------------------------

def dedup_entries(entries: list[dict]) -> list[dict]:
    """Pass 1: exact URL dedup. Pass 2: semantic dedup."""
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for e in entries:
        url = e["source_url"]
        if url in seen_urls:
            log.debug("URL dup dropped: %s", url)
            continue
        seen_urls.add(url)
        unique.append(e)
    log.info("After URL dedup: %d entries", len(unique))

    deduplicated = semantic_dedup(unique)
    log.info("After semantic dedup: %d entries", len(deduplicated))
    return deduplicated


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def sort_entries(entries: list[dict]) -> list[dict]:
    """Ascending by timestamp; null timestamps go last."""
    def sort_key(e):
        ts = e.get("publication_timestamp")
        if ts:
            return (0, ts)
        return (1, "")
    return sorted(entries, key=sort_key)


# ---------------------------------------------------------------------------
# .docx generation
# ---------------------------------------------------------------------------

def _add_horizontal_rule(doc: "Document") -> None:
    """Insert a thin horizontal line paragraph."""
    p = doc.add_paragraph()
    p_pr = p._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "999999")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def _set_heading_color(run, r: int, g: int, b: int) -> None:
    run.font.color.rgb = RGBColor(r, g, b)


def generate_docx(entries: list[dict], filename: str) -> None:
    """Build and save the .docx report."""
    if not DOCX_AVAILABLE:
        log.error("python-docx not available — skipping document generation.")
        return

    doc = Document()

    # ── Page 1: Title page ───────────────────────────────────────────────
    doc.add_paragraph()  # top margin spacer

    title_p = doc.add_heading("Russia-Ukraine War: Curated Developments", level=0)
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle_p = doc.add_paragraph()
    subtitle_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle_p.add_run(f"Report generated: {TODAY_ISO}")
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    count_p = doc.add_paragraph()
    count_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    count_run = count_p.add_run(f"Total entries: {len(entries)}")
    count_run.font.size = Pt(13)
    count_run.bold = True

    doc.add_page_break()

    # ── Page 2: Table of contents ─────────────────────────────────────────
    toc_heading = doc.add_heading("Table of Contents", level=1)
    toc_heading.alignment = WD_ALIGN_PARAGRAPH.LEFT

    for i, entry in enumerate(entries, start=1):
        toc_p = doc.add_paragraph(style="List Number")
        toc_run = toc_p.add_run(entry["title"])
        toc_run.bold = True
        label_run = toc_p.add_run(f"  —  {entry['time_period_label']}")
        label_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
        label_run.font.size = Pt(10)

    doc.add_page_break()

    # ── Per-entry sections ────────────────────────────────────────────────
    new_tag_color = RGBColor(0x00, 0x70, 0xC0)    # blue
    known_tag_color = RGBColor(0x70, 0x70, 0x70)  # grey

    for idx, entry in enumerate(entries):
        # Heading 1 — title
        h1 = doc.add_heading(entry["title"], level=1)

        # Heading 2 — timestamp + URL
        ts_display = entry["publication_timestamp"] or "Unknown date"
        h2 = doc.add_heading(level=2)
        h2.clear()
        ts_run = h2.add_run(f"{ts_display}  |  ")
        ts_run.font.size = Pt(11)
        url_run = h2.add_run(entry["source_url"])
        url_run.font.size = Pt(10)
        url_run.font.color.rgb = RGBColor(0x00, 0x56, 0xB3)

        # Body — summary
        doc.add_paragraph(entry["summary"])

        # Label line
        label_p = doc.add_paragraph()
        if entry.get("is_new_finding"):
            label_run = label_p.add_run("[NEW FINDING]")
            label_run.bold = True
            label_run.font.color.rgb = new_tag_color
        else:
            label_run = label_p.add_run("[PREVIOUSLY KNOWN]")
            label_run.bold = True
            label_run.font.color.rgb = known_tag_color

        # Separator — page break between entries except after the last
        if idx < len(entries) - 1:
            _add_horizontal_rule(doc)
            doc.add_page_break()

    doc.save(filename)
    log.info("Document saved: %s", filename)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run() -> None:
    serpapi_key = os.environ.get("SERPAPI_KEY", "").strip()
    bing_key = os.environ.get("BING_SEARCH_API_KEY", "").strip()

    if not serpapi_key and not bing_key:
        log.error(
            "No API key found. Set SERPAPI_KEY or BING_SEARCH_API_KEY "
            "environment variables before running."
        )
        sys.exit(1)

    use_serpapi = bool(serpapi_key)
    if use_serpapi:
        log.info("Using SerpAPI (primary)")
    else:
        log.info("SerpAPI key not set — using Bing Search API (fallback)")

    all_raw: list[dict] = []

    for query_spec in SEARCH_QUERIES:
        q = query_spec["q"]
        time_range = query_spec["time_range"]
        tbs = query_spec.get("tbs", "")

        if use_serpapi:
            raw_results = search_serpapi(q, serpapi_key, tbs=tbs)
            for r in raw_results:
                normalised = _normalise_serpapi(r, time_range)
                if normalised:
                    all_raw.append(normalised)
        else:
            # Bing freshness mapping (approximate)
            freshness_map = {
                "historical": "",          # Bing doesn't filter to pre-2022 easily
                "2022_invasion": "2022-02-01..2022-12-31",
                "recent": "2024-01-01..2025-12-31",
            }
            freshness = freshness_map.get(time_range, "")
            raw_results = search_bing(q, bing_key, freshness=freshness)
            for r in raw_results:
                normalised = _normalise_bing(r, time_range)
                if normalised:
                    all_raw.append(normalised)

        # Polite delay between queries to respect rate limits
        time.sleep(1.2)

    log.info("Raw results collected: %d", len(all_raw))

    # ── Deduplication ──────────────────────────────────────────────────────
    deduped = dedup_entries(all_raw)

    # ── Mark new findings (all accepted entries are "new" in a fresh run) ──
    # In a production system you would compare against a persistent store.
    # Here we mark all entries as new (is_new_finding = True) since there is
    # no prior-run database to compare against.
    for entry in deduped:
        entry["is_new_finding"] = True

    # ── Sort ───────────────────────────────────────────────────────────────
    sorted_entries = sort_entries(deduped)

    # ── Generate .docx ─────────────────────────────────────────────────────
    generate_docx(sorted_entries, OUTPUT_FILENAME)

    # ── Summary ────────────────────────────────────────────────────────────
    new_count = sum(1 for e in sorted_entries if e.get("is_new_finding"))

    dated = [e["publication_timestamp"] for e in sorted_entries if e["publication_timestamp"]]
    earliest = min(dated) if dated else "N/A"
    latest = max(dated) if dated else "N/A"

    print(f"\nTotal entries: {len(sorted_entries)}")
    print(f"New findings: {new_count}")
    print(f"Earliest timestamp: {earliest}")
    print(f"Latest timestamp: {latest}")
    print(f"Document saved: {OUTPUT_FILENAME}")


if __name__ == "__main__":
    run()
