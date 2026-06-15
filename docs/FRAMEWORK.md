# HireHunt Framework

`HireHunt` is the programmable layer behind the CLI. It gives Python code a normalized search API, source metadata, ranking, filtering, and structured result envelopes.

## Core API

```python
from hirehunt import scrape_jobs

result = scrape_jobs(
    search_term="python developer",
    sources=["naukri", "shine", "internshala"],
    city="Bengaluru",
    results_wanted=50,
)

for job in result.jobs:
    print(job)
```

## Main objects

### `Job`

Normalized job record.

Important fields:

- `title`
- `company`
- `source`
- `job_url`
- `location`
- `city`
- `country`
- `work_mode`
- `job_kind`
- `experience_min`
- `experience_max`
- `experience_text`
- `salary`
- `stipend`
- `skills`
- `description`
- `date_posted`
- `deadline`
- `company_rating`
- `company_industry`
- `apply_url`
- `match_score`
- `reasons`
- `warnings`

Rendering helpers:

- `job.display_location()`
- `job.display_experience()`
- `job.display_posted_age()`
- `job.display_compensation()`
- `job.to_compact_dict()`
- `str(job)` -> compact printable line with URL

### `ScrapeResult`

Search result container.

Important fields:

- `jobs`
- `errors`
- `stats`
- `warnings`
- `partial`
- `selected_sources`
- `schema_version`

Helpers:

- `result.top(n)`
- `result.to_dicts()`
- `result.to_compact_dicts()`
- `result.to_summary_dict()`
- `result.to_json_envelope(query=..., full=False)`
- `result.to_dataframe()`

### `JobQuery`

Normalized query object used internally by the engine and validation layer.

Key query semantics supported by the framework:

- sources or source families
- city, country, location
- company preference
- skill inclusion
- exclusion terms
- job kind
- work mode
- fresher filter
- remote filter
- experience bounds
- salary minimum
- posted-within-days
- dedupe mode and scope
- match mode

## Source architecture

The framework supports source-family expansion and config-driven registration.

### Source registry

The registry exposes:

- registered source names
- source aliases
- source families
- `SourceDefinition`
- `SourceCapabilities`

Use cases:

- ask what sources exist
- expand a family into concrete sources
- inspect pagination and filter support
- register configured variants of one adapter

### Source families

A family groups related sources under one logical adapter style.

Examples:

- `regional`
- `global`
- `faang`

This is the foundation for future adapters such as `workday`, `greenhouse`, or `institutional`.

## Result normalization

The framework normalizes:

- company names
- job URLs and apply URLs
- city and country
- location text
- skills
- posting dates
- work mode inference

That normalization happens at the model layer, not only in the CLI.

## Ranking and filtering

The framework already supports:

- weighted title/query relevance
- company and city preference
- work-mode preference
- recency signals
- salary/stipend signals
- deduplication controls
- strict, balanced, and broad match modes

## Validation and benchmarking

Framework functions:

- `validate_sources(query, sources=None)`
- `benchmark_sources(query, sources=None)`

These power both CLI diagnostics and the MCP server.

They return structured objects suitable for:

- CI
- health checks
- scheduled source monitoring
- agent diagnostics

## Python examples

### Compact JSON envelope

```python
from hirehunt import scrape_jobs

result = scrape_jobs(
    search_term="software engineer",
    city="Bengaluru",
    sources=["linkedin", "naukri"],
    results_wanted=25,
)

payload = result.to_json_envelope(
    query={"query": "software engineer", "city": "Bengaluru"},
    full=False,
)
```

### Source-family search

```python
from hirehunt import scrape_jobs

result = scrape_jobs(
    search_term="data analyst",
    source_family="regional",
    country="India",
    results_wanted=50,
)
```

### Full records

```python
records = result.to_dicts()
compact = result.to_compact_dicts()
summary = result.to_summary_dict()
```

## Boundaries

The framework is responsible for:

- discovery
- normalization
- ranking
- filtering
- export-friendly result shapes
- validation and benchmarking

It is not responsible for:

- browser login/session management
- autonomous application submission
- resume tailoring
- LLM orchestration

Those belong in an agent layer built on top of `HireHunt`.
