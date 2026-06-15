# HireHunt CLI

`hirehunt` is the human-facing interface for search, validation, benchmarking, export, and saved searches.

## Install

```bash
pip install hirehunt
```

Verify:

```bash
hirehunt -version
hirehunt -help
```

## Commands

### `hirehunt search`

Search jobs across registered sources and source families.

```bash
hirehunt search "python developer" --city Bengaluru
hirehunt search "software developer" --source naukri --source linkedin --top 10
hirehunt search "data scientist" --source-family regional --output json
```

Common search flags:

- `--source SOURCE`: repeatable concrete source selector
- `--source-family FAMILY`: expand to all sources in a family
- `--city CITY`
- `--country COUNTRY`
- `--location TEXT`
- `--company NAME`: repeatable
- `--skill NAME`: repeatable
- `--exclude TERM`: repeatable
- `--remote`
- `--fresher`
- `--job-kind {job,internship,hackathon,competition,fellowship}`
- `--work-mode {remote,hybrid,onsite,unknown}`
- `--match-mode {strict,balanced,broad}`
- `--strict-match`: alias for `--match-mode strict`
- `--related`: alias for `--match-mode broad`
- `--min-exp N`
- `--max-exp N`
- `--salary-min N`
- `--posted-days N`
- `--limit N`: fetch cap per search
- `--top N`: display cap
- `--dedupe-mode {strict,heuristic,fuzzy,none}`
- `--dedupe-scope {title-company-location,title-company-location-country,title-company}`
- `--fuzzy-dedupe`: alias for `--dedupe-mode fuzzy`
- `--cache`
- `--cache-dir PATH`

### Human output flags

- `--verbose`
- `--show-score`
- `--explain-score`
- `--show-salary`
- `--show-skills`

Default output is compact and job-seeker oriented:

```text
Found 3 jobs

1. Python Developer @ UST
   Bengaluru
   3-8 yrs
   Today
   Naukri
   https://example.com/job
```

### Machine-readable output

- `--output text|json|json-full`
- `--json-stdout`: alias for `--output json`
- `--summary-json`
- `--no-pretty`
- `--csv FILE`
- `--csv-full FILE`
- `--json FILE`
- `--json-full FILE`

Examples:

```bash
hirehunt search "python developer" --city Bengaluru --output json
hirehunt search "python developer" --city Bengaluru --summary-json
hirehunt search "python developer" --city Bengaluru --csv jobs.csv
```

Search exit behavior:

- `0`: success
- `3`: no jobs
- `4`: partial/source-error result
- `5`: output failure

### `hirehunt validate`

Run live fetch and parser checks against selected sources.

```bash
hirehunt validate "python developer" --source naukri --source linkedin
hirehunt validate "python developer" --source-family regional --strict --min-parsed 5
```

Validation flags:

- `--report FILE`
- `--strict`
- `--min-parsed N`
- `--max-failures N`

### `hirehunt benchmark`

Measure source throughput and request volume.

```bash
hirehunt benchmark "python developer" --source naukri
hirehunt benchmark "python developer" --source-family global --strict --min-jobs-per-second 1.0
```

Benchmark flags:

- `--report FILE`
- `--strict`
- `--min-parsed N`
- `--min-jobs-per-second N`
- `--max-requests N`

### `hirehunt saved-search`

Persist reusable search definitions.

```bash
hirehunt saved-search add py-blr "python developer" --city Bengaluru --related
hirehunt saved-search list
hirehunt saved-search show py-blr
hirehunt saved-search run py-blr --top 5
hirehunt saved-search remove py-blr
```

Saved-search subcommands:

- `add`
- `list`
- `show`
- `run`
- `remove`

Saved searches are stored in a JSON registry. Override with:

```bash
hirehunt saved-search --file C:\path\to\saved-searches.json list
```

## Notes

- `--limit 0` means exhaustive fetch where the source supports it. Use it carefully on broad queries.
- `--top` controls terminal rendering only. It does not reduce fetched results.
- `--output json` and `--summary-json` are the right choices when another program is consuming the CLI.
