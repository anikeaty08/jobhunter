# `utils/` — Shared Utilities

Low-level helpers used by all scrapers and the engine.

## Modules

| File | Purpose |
|---|---|
| `fetchers.py` | `CachedFetcher` — HTTP client with proxy support, optional disk cache, multiple backends |
| `normalization.py` | Text cleaning, money parsing, city normalization, skill extraction, date parsing |
| `cache.py` | Disk-based response cache (keyed by URL + params) |
| `dedupe.py` | Duplicate job detection by URL and title+company fingerprint |
| `http.py` | Low-level request helpers, retry logic, User-Agent rotation |

## Key Functions — `normalization.py`

```python
from jobhunter.utils.normalization import (
    clean_text,         # Strip HTML, excess whitespace, control chars
    normalize_city,     # "bengaluru" → "Bengaluru", "blr" → "Bengaluru"
    normalize_skills,   # ["Python ", "  SQL", "python"] → ["python", "sql"]
    normalize_url,      # Clean tracking params, ensure https://
    parse_money,        # "₹4-6 LPA" → Money(min=400000, max=600000, period=YEAR)
    parse_date,         # "2 days ago", "Jun 5, 2026" → "2026-06-07"
    parse_work_mode,    # "remote", "wfh", "hybrid" → WorkMode enum
    parse_job_kind,     # "intern", "hackathon" → JobKind enum
    parse_experience,   # "3-5 years" → (3.0, 5.0, "3-5 years")
)
```

## Key Class — `CachedFetcher`

```python
from jobhunter.utils.fetchers import CachedFetcher

fetcher = CachedFetcher(
    source="my_source",
    backend="requests",      # "requests" only for now
    proxies=["http://..."],  # optional proxy list
    cache_enabled=True,      # cache responses to disk
    cache_dir=".jobhunter_cache",
)

resp = fetcher.fetch("https://example.com/page")      # HTML GET
resp = fetcher.get_json("https://api.example.com/jobs", params={"q": "python"})
resp = fetcher.post_json("https://api.example.com/graphql", payload={...})

# FetchResponse
resp.status_code   # int
resp.text          # str — raw response body
resp.backend       # str — which backend served it
```

## City Aliases (`normalize_city`)

Common Indian city aliases are normalized:

| Input | Output |
|---|---|
| `blr`, `bangalore`, `bengaluru` | `Bengaluru` |
| `mum`, `mumbai`, `bombay` | `Mumbai` |
| `del`, `delhi`, `new delhi` | `Delhi` |
| `hyd`, `hyderabad` | `Hyderabad` |
| `chn`, `chennai`, `madras` | `Chennai` |
| `pun`, `pune` | `Pune` |

## Deduplication (`dedupe.py`)

Jobs are deduplicated in two passes:

1. **Exact URL match** — same `job_url` → drop duplicate
2. **Fuzzy fingerprint** — same `(normalized_title, normalized_company)` within same source → drop
