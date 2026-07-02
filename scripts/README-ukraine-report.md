# Russia-Ukraine War Report Generator

`fetch_ukraine_war_report.py` searches for Russia-Ukraine War developments
across three time ranges, deduplicates results, and writes a structured
`.docx` report to the working directory.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r scripts/requirements-ukraine-report.txt
```

### 2. Set your API key

**Option A — SerpAPI (primary)**

```bash
export SERPAPI_KEY="your_serpapi_key_here"
```

Get a free key at <https://serpapi.com/>.

**Option B — Bing Search API (fallback)**

```bash
export BING_SEARCH_API_KEY="your_bing_key_here"
```

Get a key via [Azure Cognitive Services](https://portal.azure.com/).

The script uses SerpAPI if `SERPAPI_KEY` is set; otherwise it falls back to
Bing. At least one key must be present.

### 3. Run

```bash
python scripts/fetch_ukraine_war_report.py
```

On success you will see output similar to:

```
Total entries: 73
New findings: 73
Earliest timestamp: 2014-02-27T00:00:00Z
Latest timestamp: 2025-05-18T09:14:00Z
Document saved: russia_ukraine_war_2025-05-22.docx
```

---

## What It Does

| Step | Description |
|------|-------------|
| **Search** | Runs 9 queries (3 per time range: historical, 2022 invasion, recent) against SerpAPI or Bing, retrieving ≥ 10 results per query |
| **Normalise** | Extracts `title`, `source_url`, `publication_timestamp` (ISO 8601), `summary`, `time_period_label`, `is_new_finding` for every result |
| **Dedup pass 1** | Exact URL deduplication — discards any entry whose URL was already seen |
| **Dedup pass 2** | TF-IDF cosine similarity on `summary` fields — discards entries with similarity > 0.85 to any already-accepted entry (no NumPy required) |
| **Sort** | Ascending chronological order; `null` timestamps last |
| **Generate** | `.docx` with title page, table of contents, and one section per entry |

---

## Output Document Structure

| Section | Content |
|---------|---------|
| Page 1 — Title page | Centred heading, generation date, total entry count |
| Page 2 — Table of contents | Numbered list of entry titles with `time_period_label` |
| Subsequent pages | Heading 1 (title), Heading 2 (timestamp + URL), body (summary), bold label `[NEW FINDING]` or `[PREVIOUSLY KNOWN]`, horizontal rule / page break between entries |

The filename is `russia_ukraine_war_YYYY-MM-DD.docx` (today's date).

---

## Search Queries

### Historical / Origins (Pre-2022)
- `Russia Ukraine conflict history pre-2022`
- `Crimea annexation 2014 Russia Ukraine`
- `Donbas conflict origins separatists Ukraine`

### 2022 Invasion
- `Russia Ukraine invasion February 2022`
- `Kyiv offensive 2022 Russian forces retreat`
- `Ukraine war 2022 timeline battles Mariupol`

### Recent / Ongoing (2024–2025)
- `Russia Ukraine war latest news 2024`
- `Ukraine frontline update 2025 Zaporizhzhia Kherson`
- `Russia Ukraine ceasefire negotiations peace talks 2025`

---

## Error Handling

- HTTP errors and JSON decode errors are logged as warnings and processing continues
- API rate limits trigger exponential back-off (up to 3 retries per query)
- Missing fields are gracefully handled: `publication_timestamp` defaults to `null`, `summary` falls back to title + snippet
- If `python-docx` is not installed the script exits with an installation hint

---

## Notes

- Generated `.docx` files are excluded from version control (see `.gitignore`)
- `is_new_finding` is `true` for all entries in a fresh run; in a production
  system you would persist the URL list between runs and compare against it
- The TF-IDF deduplication is implemented with the standard library only
  (`collections.Counter`, `math`) — no NumPy or SciPy required
