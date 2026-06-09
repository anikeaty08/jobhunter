# `jobhunter/` — Core Package

The main Python package. All public APIs are exported from `__init__.py`.

## Module Map

| File | Purpose |
|---|---|
| `__init__.py` | Top-level `scrape_jobs()` function — the main entry point |
| `models.py` | All data classes: `Job`, `Money`, `WorkMode`, `JobKind`, `SalaryPeriod` |
| `query.py` | `JobQuery` and `JobProfile` — unified search parameters |
| `engine.py` | `SearchEngine` — parallel scraping, dedup, filter, rank pipeline |
| `registry.py` | `ScraperRegistry` — maps source names → scraper classes |
| `filtering.py` | Soft filtering by salary, city, skills, date, experience |
| `ranking.py` | `match_score` relevance scoring against a `JobProfile` |
| `validation.py` | Input validation for queries and results |
| `exceptions.py` | `UnknownSourceError` and other custom exceptions |
| `cli.py` | `jobhunter` CLI — powered by `argparse` / `rich` |

## Subpackages

```
scrapers/    ← one file per job source
exporters/   ← csv, json, pandas DataFrame
utils/       ← HTTP fetcher, normalization helpers, cache, dedup
```

## Key Design Decisions

- **Every scraper returns `list[Job]`** — same shape regardless of source
- **Filters are soft** — if a job is missing a field (e.g. no salary data), it passes through rather than being dropped
- **Scraping is parallel** — `engine.py` runs all sources concurrently via `ThreadPoolExecutor`
- **Registry-driven** — adding a new source = one file + one line in `scrapers/__init__.py`

## Usage

```python
from jobhunter import scrape_jobs

jobs = scrape_jobs(
    search_term="python developer",
    sources=["naukri", "shine", "linkedin"],
    city="Bengaluru",
    results_wanted=50,
)
```
