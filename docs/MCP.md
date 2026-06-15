# HireHunt MCP Server

`hirehunt-mcp` exposes the `HireHunt` framework as MCP tools so an agent can search jobs, inspect source metadata, validate sources, benchmark sources, and run saved searches without scraping terminal text.

## Why MCP here

CLI output is optimized for humans.

MCP is optimized for agents because it returns:

- structured tool results
- explicit summaries
- explicit errors
- reusable source metadata
- saved-search execution without shell parsing

## Entry point

Install the package:

```bash
pip install hirehunt
```

Run the server:

```bash
hirehunt-mcp
```

Optional:

```bash
hirehunt-mcp --saved-searches-file C:\path\to\saved-searches.json
```

The server speaks MCP over `stdio`. It supports normal MCP `Content-Length` framing and also accepts newline-delimited JSON for local debugging.

## Server identity

- server name: `hirehunt-mcp`
- version: package version, currently `0.5.0`
- protocol version: `2024-11-05`

## Available tools

### `search_jobs`

Search jobs and return a structured result envelope.

Inputs:

- `query` required
- `sources`
- `source_family`
- `city`
- `country`
- `location`
- `company`
- `skills`
- `exclude`
- `job_kind`
- `work_mode`
- `match_mode`
- `limit`
- `dedupe_mode`
- `dedupe_scope`
- `remote`
- `fresher`
- `min_exp`
- `max_exp`
- `salary_min`
- `posted_days`

Returns:

- `ok`
- `status`
- `meta`
- `query`
- `summary`
- `jobs`

This is the primary tool an agent should call.

### `list_sources`

List every concrete registered source.

Each source includes:

- `name`
- `family`
- `adapter`
- `aliases`
- `tags`
- `config`
- `capabilities`

Use this when the agent needs to plan source selection instead of hardcoding names.

### `list_source_families`

List families and the concrete sources in each family.

Useful for planning broad searches such as `regional` or `global`.

### `get_source_definition`

Get the full metadata for one source.

Use this when the agent needs to understand:

- supported filters
- whether pagination exists
- whether exhaustive search is supported
- what family/adapter the source belongs to

### `validate_sources`

Run live validation against selected sources.

Returns per-source:

- status code
- backend
- fetched flag
- parsed count
- sample titles
- error
- `ok`

This is the right tool for agent health checks or diagnostics.

### `benchmark_sources`

Run throughput benchmarking.

Returns per-source:

- duration
- requests
- parsed count
- jobs per second
- completion
- completion reason
- error

Use this for performance monitoring or source-health evaluation.

### `save_search`

Persist a named search definition for later use.

### `list_saved_searches`

List saved searches known to the server.

### `get_saved_search`

Get one saved search by name.

### `run_saved_search`

Execute a saved search and return the same envelope as `search_jobs`.

## Result shape

The server returns tool results with:

- human-readable `content`
- machine-readable `structuredContent`
- `isError`

For search tools, `structuredContent.data` contains the real payload.

Example result shape:

```json
{
  "tool": "search_jobs",
  "data": {
    "ok": true,
    "status": "ok",
    "meta": {
      "format": "json",
      "schema_version": "1.0"
    },
    "query": {
      "query": "python developer",
      "sources": ["naukri"],
      "city": "Bengaluru",
      "limit": 20
    },
    "summary": {
      "job_count": 20,
      "partial": false,
      "selected_sources": ["naukri"],
      "warnings": [],
      "errors": {},
      "source_summary": {
        "naukri": {
          "kept": 20,
          "parsed": 20,
          "duplicates": 0,
          "filtered_out": 0,
          "requests": 1,
          "completion": "capped",
          "completion_reason": "results_wanted=20",
          "filter_reasons": {}
        }
      },
      "filter_reasons": {}
    },
    "jobs": [
      {
        "title": "Python Developer",
        "company": "UST",
        "source": "naukri",
        "job_url": "https://example.com/job",
        "display_location": "Bengaluru",
        "experience": "3-8 yrs",
        "posted": "Today",
        "compensation": "INR 8-12 LPA",
        "company_rating": "",
        "company_industry": "",
        "match_score": 45.0,
        "reasons": [],
        "warnings": []
      }
    ]
  }
}
```

## Agent guidance

Recommended sequence:

1. `list_sources` or `list_source_families`
2. `search_jobs`
3. inspect `summary.source_summary`
4. if quality is suspicious, call `validate_sources`
5. persist reusable searches with `save_search`

For broad automation:

- use concrete `sources` when you need predictability
- use `source_family` when you want broader coverage
- inspect `summary.errors` and `summary.partial`
- inspect `source_summary[*].completion`

## Example MCP client configuration

Generic local stdio configuration:

```json
{
  "mcpServers": {
    "hirehunt": {
      "command": "hirehunt-mcp",
      "args": []
    }
  }
}
```

With a custom saved-searches registry:

```json
{
  "mcpServers": {
    "hirehunt": {
      "command": "hirehunt-mcp",
      "args": [
        "--saved-searches-file",
        "C:\\Users\\you\\.hirehunt\\saved-searches.json"
      ]
    }
  }
}
```

If the executable is not on `PATH`, point the command at Python:

```json
{
  "mcpServers": {
    "hirehunt": {
      "command": "python",
      "args": ["-m", "hirehunt.mcp_server"]
    }
  }
}
```

## Boundaries

This MCP server exposes discovery and diagnostics.

It does not perform:

- browser automation
- login/session handling
- resume tailoring
- autonomous application submission

Those belong in an agent layer that calls this server as one tool among several.
