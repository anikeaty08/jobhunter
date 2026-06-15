# HireHunt

**A programmable job-search aggregation framework for India and global markets.**

HireHunt provides:

- A stable normalized job schema.
- Source-family registration with machine-readable capabilities and definitions.
- Synchronous and asynchronous orchestration.
- Configurable filtering, ranking, deduplication, retry, and caching policies.
- Per-source completion and filtering diagnostics.
- Graceful partial results when one source fails.
- Fixture-based parser contract tests, optional live validation, and benchmark reporting.

## Documentation

- [CLI guide](docs/CLI.md)
- [Framework guide](docs/FRAMEWORK.md)
- [MCP server guide](docs/MCP.md)

---

## Sources

| Source | Region | Type | Method |
|---|---|---|---|
| `naukri` | 🇮🇳 India | Jobs | REST API — 15,000+ listings |
| `shine` | 🇮🇳 India | Jobs | SSR JSON — 17,000+ listings |
| `internshala` | 🇮🇳 India | Internships / Jobs | HTML scraping |
| `unstop` | 🇮🇳 India | Hackathons / Competitions | REST API |
| `linkedin` | 🌍 Global | Jobs | Guest HTML API |
| `indeed` | 🌍 Global | Jobs | GraphQL API |
| `google_careers` | 🌍 FAANG | Jobs | LinkedIn (company-filtered) |
| `amazon` | 🌍 FAANG | Jobs | REST API |
| `meta` | 🌍 FAANG | Jobs | LinkedIn (company-filtered) |
| `apple` | 🌍 FAANG | Jobs | LinkedIn (keyword search) |
| `netflix` | 🌍 FAANG | Jobs | LinkedIn (company-filtered) |
| `microsoft` | 🌍 FAANG | Jobs | LinkedIn (company-filtered) |

---

## Installation

```bash
pip install hirehunt
```

The primary import is `hirehunt`. A top-level `jobhunter` compatibility shim
is also packaged for existing users.

**Requirements:** Python 3.10+

---

## Quick Start

### Python API

```python
from hirehunt import scrape_jobs

# Search across India's top job boards
result = scrape_jobs(
    search_term="python developer",
    sources=["naukri", "shine", "internshala"],
    city="Bengaluru",
    results_wanted=50,
)

for job in result.jobs:
    print(job)
# Python Developer @ TCS | Bengaluru | naukri | https://...
# Python Developer @ Infosys | Bengaluru | shine | https://...
```

### CLI

```bash
# India job search
hirehunt search "data scientist" --city Mumbai --source naukri --source shine

# Company-aware search
hirehunt search "software engineer" --company DRDO --source linkedin --country India

# Hackathons & competitions
hirehunt search "hackathon" --source unstop

# FAANG company jobs
hirehunt search "software engineer" --source google_careers --source amazon

# Expand a whole source family
hirehunt search "backend developer" --source-family aggregator --country India

# Search with stronger matching and freshness filters
hirehunt search "python developer" --city Bengaluru --posted-days 7 --max-exp 5 --match-mode strict

# Benchmark a family
hirehunt benchmark "python developer" --source-family regional --country India --limit 10

# Fail on health regressions
hirehunt validate "software engineer" --source-family aggregator --country India --strict --min-parsed 1

# Export to CSV
hirehunt search "backend developer" --source naukri --source linkedin --csv jobs.csv

# Export to JSON
hirehunt search "backend developer" --source naukri --source linkedin --json jobs.json

# Agent-native JSON to stdout
hirehunt search "backend developer" --source naukri --output json
hirehunt search "backend developer" --source naukri --json-stdout
hirehunt search "backend developer" --source naukri --summary-json

# Fuzzy cross-source dedupe
hirehunt search "software developer" --source naukri --source linkedin --dedupe-mode fuzzy --dedupe-scope title-company-location

# Saved searches / bookmarks
hirehunt saved-search add python-blr "python developer" --city Bengaluru --related --fuzzy-dedupe
hirehunt saved-search list
hirehunt saved-search show python-blr
hirehunt saved-search run python-blr --output json

# Top 20 ranked results
hirehunt search "machine learning" --source naukri --source shine --top 20
```

Default search output is optimized for fast scanning:

```text
Found 32 jobs

1. Python Developer @ UST
   Bengaluru
   3-5 yrs
   Today
   INR 4-6 LPA
   Naukri
```

Use `--verbose`, `--show-score`, `--show-salary`, `--show-skills`, or
`--explain-score` for expanded output.

Machine-readable stdout is available through `--output json`, `--json-stdout`,
`--summary-json`, and `--no-pretty`.

Search exit codes are stable:

- `0`: success with jobs
- `3`: no jobs found
- `4`: partial results or source errors
- `5`: output/export failure

---

## Result Limits And Completion

`results_wanted` is a per-source policy:

```python
results_wanted=50    # At most 50 parsed records per source
results_wanted=0     # Exhaustive mode
results_wanted=None  # Exhaustive mode
```

Exhaustive mode continues until the source returns no further results. Some
sources cannot guarantee exhaustive public search. Inspect the completion
metadata rather than assuming every result is complete:

```python
for source, stats in result.stats.items():
    print(source, stats.completion, stats.completion_reason)
```

Completion values are `exhausted`, `capped`, `partial`, `failed`, or `unknown`.
Broad exhaustive searches on Naukri or Shine can require many requests.

## Python API Reference

### `scrape_jobs()`

```python
from hirehunt import scrape_jobs

result = scrape_jobs(
    search_term="python developer",   # What to search
    sources=["naukri", "shine"],      # Which sources (list or "auto")
    source_family="",                 # Optional family expansion, e.g. "aggregator"
    company="Acme",                   # Optional company intent
    city="Bengaluru",                 # City filter (optional)
    location="India",                 # Broader location (optional)
    country="India",                  # Country (optional)
    results_wanted=50,                # Max per source; None or 0 = exhaustive
    dedupe_mode="strict",             # "strict", "heuristic", "fuzzy", or "none"
    dedupe_scope="title-company-location-country",
    job_kind="job",                   # "job", "internship", "hackathon"
    remote=None,                      # True = remote only
    work_mode=None,                   # "remote", "hybrid", "onsite", "unknown"
    salary_min=500000,                # Min salary in INR (optional)
    posted_within_days=30,            # Only jobs from last N days
    skills=["python", "django"],      # Skill filter (optional)
    experience_min=0,                 # Min years experience (optional)
    experience_max=5,                 # Max years experience (optional)
    request_policy={                  # Optional retry/rate policy
        "retries": 4,
        "timeout": 25,
        "backoff_base": 2,
        "min_delay": 0.2,
        "max_delay": 0.8,
    },
)
```

The return value is a `ScrapeResult`, not a bare list:

```python
result.jobs
result.errors
result.warnings
result.partial
result.selected_sources
result.stats
```

Framework-level rendering helpers are now available directly on the models:

```python
job.display_location()
job.display_experience()
job.display_posted_age()
job.display_compensation()
job.to_compact_dict()

result.to_summary_dict()
result.to_json_envelope(query={"role": "python developer"})
```

### `Job` Object

Every source returns the same normalized `Job` dataclass:

```python
@dataclass
class Job:
    schema_version: ClassVar[str]  # currently "1.0"
    title: str
    company: str
    source: str
    job_url: str

    location: str
    city: str
    country: str
    work_mode: WorkMode         # "remote" | "hybrid" | "onsite" | "unknown"
    job_kind: JobKind           # "job" | "internship" | "hackathon" | "competition"

    salary: Money               # min_amount, max_amount, currency, period
    stipend: Money

    skills: list[str]
    experience_min: float | None
    experience_max: float | None
    description: str
    date_posted: str | None
    deadline: str | None        # for competitions/hackathons

    match_score: float          # 0.0–100.0 after ranking
```

`Job.to_dict()` includes `schema_version`. Additive fields may be introduced
without changing the meaning of existing fields. Breaking schema changes
require a new schema version.

### Source Diagnostics

Every `SourceStats` includes:

```python
stats.fetched
stats.parsed
stats.found                 # Backward-compatible parsed count
stats.filtered_out
stats.kept
stats.duplicates
stats.errors
stats.requests
stats.completion
stats.completion_reason
stats.filter_reasons        # e.g. {"city_mismatch": 12}
```

If one source fails, successful source results are still returned and
`result.partial` is set to `True`.

### Source Capabilities

Sources declare supported countries, job kinds, native filters, pagination,
and exhaustive-search support:

```python
from hirehunt.registry import default_registry

registry = default_registry()
print(registry.capabilities("naukri"))
print(registry.capabilities())  # all sources
```

Custom scrapers declare the same contract:

```python
from hirehunt.models import JobKind, SourceCapabilities
from hirehunt.scrapers.base import BaseScraper

class MyScraper(BaseScraper):
    source = "my_source"
    capabilities = SourceCapabilities(
        countries=("India",),
        job_kinds=(JobKind.JOB,),
        supported_filters=frozenset({"city"}),
        pagination=True,
        exhaustive_search=True,
        description="My source adapter",
    )

    def search(self, query):
        ...
```

### Source Definitions

The registry now exposes source-family metadata for config-driven expansion:

```python
from hirehunt.registry import default_registry

registry = default_registry()
print(registry.families())                  # ['aggregator', 'company', 'opportunity', 'regional']
print(registry.family_sources("regional"))  # ['internshala', 'naukri', 'shine']
print(registry.definition("linkedin"))      # SourceDefinition(...)
```

Families are reusable framework groupings, not one-off scraper classes. New
adapters such as `workday`, `greenhouse`, or `institutional` can slot into the
same contract without changing `SearchEngine`.

Config-driven expansion uses `register_configured_source()` so one adapter can
back many portals:

```python
from hirehunt.registry import ScraperRegistry
from hirehunt.scrapers.base import BaseScraper

registry = ScraperRegistry()
registry.register_configured_source(
    MyWorkdayScraper,
    source="acme_workday",
    family="workday",
    aliases=("acme",),
    config={"tenant": "acme", "site": "Careers"},
)
```

### Pluggable Policies

`SearchEngine` accepts a `SearchPolicies` bundle:

```python
from hirehunt import SearchEngine
from hirehunt.policies import SearchPolicies
from hirehunt.query import JobQuery

engine = SearchEngine(
    policies=SearchPolicies(
        filtering=my_filter_policy,
        ranking=my_rank_policy,
        deduplication=my_dedupe_policy,
    )
)
query = JobQuery(search_term="backend developer", sources=["naukri", "shine"])
result = engine.search(query)
```

Policy contracts return `FilterOutcome` and `DedupeOutcome`, preserving
diagnostics while allowing custom behavior.

Deduplication modes available through `JobQuery`:

- `strict`: normalized URL, then source ID, then fallback identity.
- `heuristic`: normalized title, company, location, and country across sources.
- `fuzzy`: near-title matching plus company/location identity.
- `none`: retain every parsed record.

`dedupe_scope` controls which identity fields are used for heuristic and fuzzy
dedupe. Available scopes are:

- `title-company-location-country`
- `title-company-location`
- `title-company`

## CLI JSON Contract

For automation agents, `hirehunt search --output json` writes a stable envelope
to stdout:

```json
{
  "ok": true,
  "status": "ok",
  "exit_code": 0,
  "command": "search",
  "version": "0.5.0",
  "meta": {
    "format": "json",
    "schema_version": "1.0"
  },
  "query": {},
  "summary": {
    "job_count": 0,
    "warnings": [],
    "errors": {},
    "source_summary": {},
    "filter_reasons": {}
  },
  "jobs": []
}
```

`--summary-json` emits the same summary contract without the full job list.
`--no-pretty` upgrades plain text mode into the JSON envelope automatically.

CLI parse and output failures also return machine-readable envelopes when a
machine mode is requested.

## Saved Searches

Saved searches provide lightweight bookmark support for the CLI:

```bash
hirehunt saved-search add backend-blr "backend developer" --city Bengaluru --related
hirehunt saved-search list
hirehunt saved-search show backend-blr
hirehunt saved-search run backend-blr
hirehunt saved-search remove backend-blr
```

### Retry And Rate Policy

```python
from hirehunt import JobQuery, RequestPolicy

query = JobQuery(
    search_term="backend developer",
    request_policy=RequestPolicy(
        retries=4,
        timeout=25,
        backoff_base=2,
        min_delay=0.2,
        max_delay=0.8,
    ),
)
```

### Custom Cache Backend

Pass any object implementing `get(source, key)` and
`set(source, key, content, status_code=200)`:

```python
query = JobQuery(
    search_term="python",
    cache_enabled=True,
    cache_backend=my_cache,
)
```

### Export

```python
from hirehunt import scrape_jobs
from hirehunt.exporters.csv import to_csv
from hirehunt.exporters.dataframe import to_dataframe
from hirehunt.exporters.json import to_json

result = scrape_jobs(search_term="python developer", sources=["naukri", "shine"])

to_csv(result.jobs, "jobs.csv")
to_json(result.jobs, "jobs.json")
df = to_dataframe(result.jobs)
```

---

## Project Structure

```
hirehunt/
├── __init__.py          # scrape_jobs() entry point
├── models.py            # Job, Money, WorkMode, JobKind dataclasses
├── query.py             # JobQuery — unified search parameters
├── engine.py            # Orchestrates parallel scraping + dedup
├── registry.py          # Scraper registry + auto-source selection
├── filtering.py         # Soft filtering (salary, city, skills, date)
├── ranking.py           # Relevance scoring / match_score
├── policies.py          # Injectable framework policy contracts
├── validation.py        # Live source validation
├── exceptions.py        # Custom exceptions
├── cli.py               # `jobhunter` CLI entry point
│
├── scrapers/
│   ├── base.py          # BaseScraper ABC
│   ├── naukri.py        # 🇮🇳 Naukri — /jobapi/v2/search REST API
│   ├── shine.py         # 🇮🇳 Shine — __NEXT_DATA__ SSR JSON
│   ├── internshala.py   # 🇮🇳 Internshala — HTML + pagination
│   ├── unstop.py        # 🇮🇳 Unstop — hackathons REST API
│   ├── linkedin.py      # 🌍 LinkedIn — guest HTML API
│   ├── indeed.py        # 🌍 Indeed — GraphQL API
│   └── faang.py         # 🌍 Google, Amazon, Meta, Apple, Netflix, Microsoft
│
├── exporters/
│   ├── csv_exporter.py
│   ├── json_exporter.py
│   └── dataframe.py
│
└── utils/
    ├── fetchers.py      # CachedFetcher with proxy + backend support
    └── normalization.py # clean_text, parse_money, normalize_city, ...

tests/
```

---

## Source Details

### 🇮🇳 Naukri
- **Endpoint:** `GET https://www.naukri.com/jobapi/v2/search`
- **Auth:** Session cookies from page warm-up (automatic)
- **Fields:** Title, company, salary (LPA), location, skills, experience, date
- **Pagination:** `pageNo=N`, 20 results/page, 3,000+ pages available

### 🇮🇳 Shine
- **Endpoint:** `__NEXT_DATA__` SSR JSON embedded in HTML
- **Fields:** `jJT` (title), `jCName` (company), `jSal` (salary), `jLoc` (location), `jKwd` (skills), `jPDate` (date), `jSlug` (URL)
- **Pagination:** path suffix `-N`, 20 results/page

### 🇮🇳 Internshala
- **Endpoint:** HTML scraping — `div[id^='individual_internship_'][internshipid]`
- **Pagination:** `?page=N`, 40+ cards/page
- **City filter:** current SEO routes, e.g. `/internships/python-internship-in-bangalore/`

### 🇮🇳 Unstop
- **Endpoint:** `GET https://unstop.com/api/public/opportunity/search-result`
- **Note:** Returns hackathons, coding competitions, and challenges only
- **Fields:** Title, organisation, skills, location, deadline, prize

### 🌍 Indeed
- **Endpoint:** `POST https://apis.indeed.com/graphql`
- **Auth:** Public API key (included)
- **Pagination:** Cursor-based

### 🌍 LinkedIn
- **Endpoint:** `GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search`
- **Auth:** None — guest API
- **FAANG filter:** `f_C` company ID parameter

### 🌍 Amazon
- **Endpoint:** `GET https://www.amazon.jobs/en/search.json`
- **Auth:** None — public REST API

---

## Filtering

Most structured-data filters are soft: missing salary, skills, experience, or
location data does not automatically remove a job. Explicit remote and posting
date filters are strict.

```python
result = scrape_jobs(
    "python developer",
    sources=["naukri", "shine"],
    salary_min=600_000,        # Only applied if salary data exists
    city="Bengaluru",          # Only applied if location data exists
    skills=["python", "sql"],  # Only applied if skills data exists
    posted_within_days=14,     # Missing or invalid dates are removed
)
```

---

## Advanced Usage

### FAANG-only search

```python
from hirehunt import scrape_jobs
from hirehunt.registry import default_registry

registry = default_registry()
faang = registry.faang_sources()  # ['google_careers', 'amazon', 'meta', 'apple', 'netflix', 'microsoft']

result = scrape_jobs(
    search_term="software engineer",
    sources=faang,
    results_wanted=20,
)
```

### Parallel scraping with custom config

```python
result = scrape_jobs(
    search_term="backend developer",
    sources=["naukri", "shine", "linkedin"],
    city="Hyderabad",
    results_wanted=100,
    posted_within_days=7,
    cache_enabled=True,        # Cache responses locally
    proxies=["http://..."],    # Optional proxy list
)
```

### Auto-source selection

```python
# Automatically picks India job sources when country="India"
result = scrape_jobs(
    search_term="python developer",
    country="India",
    sources="auto",  # → [indeed, linkedin, internshala, naukri, shine]
)
```

Opportunity terms such as `hackathon`, `competition`, or `challenge`
automatically add Unstop.

## Testing And Validation

```bash
pip install -e .
python -m unittest discover -s tests -v
hirehunt validate "software developer" --city Bengaluru --country India
hirehunt benchmark "software developer" --source-family aggregator --country India --limit 5
```

Parser contracts use sanitized fixtures under `tests/fixtures`. Live validation
is separate because remote sites can block, rate-limit, or change independently
of deterministic unit tests.

CI runs the deterministic suite across Python 3.10-3.13 in
`.github/workflows/ci.yml`. Scheduled source monitoring and parser-drift alerts
run through `.github/workflows/source-health.yml`, which executes `validate` and
`benchmark` for each source family and uploads the resulting JSON reports.
`.github/workflows/publish.yml` gates release publication on tests, successful
builds, and a wheel-install smoke run.

## Compatibility

Existing public fields and calls remain supported:

- `scrape_jobs(**kwargs)` and `search_jobs(**kwargs)`.
- `result.jobs`, `result.errors`, `result.stats`, and `result.warnings`.
- `SourceStats.found`, `kept`, `duplicates`, and `errors`.
- `filter_jobs`, `rank_jobs`, and `deduplicate_jobs`.

New metadata and policy APIs are additive.

## License

MIT
