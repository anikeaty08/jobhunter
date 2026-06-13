"""Command line interface for HireHunt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from hirehunt import __version__
from hirehunt.engine import search_jobs
from hirehunt.exporters.csv import to_csv
from hirehunt.exporters.json import to_json
from hirehunt.models import Job
from hirehunt.query import JobQuery
from hirehunt.validation import (
    HealthThresholds,
    benchmark_sources,
    evaluate_benchmark_health,
    evaluate_validation_health,
    validate_sources,
    write_benchmark_report,
    write_validation_report,
)

EXIT_OK = 0
EXIT_HEALTH_FAILURE = 1
EXIT_USAGE_ERROR = 2
EXIT_NO_JOBS = 3
EXIT_PARTIAL_RESULTS = 4
EXIT_OUTPUT_ERROR = 5

DEFAULT_SAVED_SEARCHES = "saved_searches.json"


class CliUsageError(Exception):
    """Raised when CLI parsing should return a structured error."""


class CliParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - argparse path
        raise CliUsageError(message)


def _new_parser(*args, **kwargs) -> argparse.ArgumentParser:
    kwargs.setdefault("add_help", False)
    parser = CliParser(*args, **kwargs)
    parser.add_argument("-help", "--help", action="help", help="Show this help message and exit")
    parser.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = _new_parser(
        prog="hirehunt",
        description="Search and validate jobs across India and global sources.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search jobs across sources", add_help=False)
    search.add_argument("-help", "--help", action="help", help="Show this help message and exit")
    search.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    _add_query_args(search)
    _add_display_args(search)

    validate = subparsers.add_parser("validate", help="Validate live source fetching and parsing", add_help=False)
    validate.add_argument("-help", "--help", action="help", help="Show this help message and exit")
    validate.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    _add_query_args(validate)
    validate.add_argument("--report", default="", metavar="FILE", help="Write JSON validation report")
    _add_health_args(validate)

    benchmark = subparsers.add_parser("benchmark", help="Benchmark source speed and request volume", add_help=False)
    benchmark.add_argument("-help", "--help", action="help", help="Show this help message and exit")
    benchmark.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    _add_query_args(benchmark)
    benchmark.add_argument("--report", default="", metavar="FILE", help="Write JSON benchmark report")
    _add_health_args(benchmark)

    saved = subparsers.add_parser("saved-search", help="Manage saved searches", add_help=False)
    saved.add_argument("-help", "--help", action="help", help="Show this help message and exit")
    saved.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    saved.add_argument("--file", default=DEFAULT_SAVED_SEARCHES, help="Saved search registry JSON file")
    saved_subparsers = saved.add_subparsers(dest="saved_command", required=True)

    saved_add = saved_subparsers.add_parser("add", help="Save a named search", add_help=False)
    saved_add.add_argument("-help", "--help", action="help", help="Show this help message and exit")
    saved_add.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    saved_add.add_argument("name", help="Saved search name")
    _add_query_args(saved_add)
    _add_saved_search_fields(saved_add)
    _add_saved_search_display_prefs(saved_add)

    saved_list = saved_subparsers.add_parser("list", help="List saved searches", add_help=False)
    saved_list.add_argument("-help", "--help", action="help", help="Show this help message and exit")
    saved_list.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    saved_list.add_argument("--json", action="store_true", help="Emit saved searches as JSON")

    saved_show = saved_subparsers.add_parser("show", help="Show one saved search", add_help=False)
    saved_show.add_argument("-help", "--help", action="help", help="Show this help message and exit")
    saved_show.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    saved_show.add_argument("name", help="Saved search name")

    saved_remove = saved_subparsers.add_parser("remove", help="Remove one saved search", add_help=False)
    saved_remove.add_argument("-help", "--help", action="help", help="Show this help message and exit")
    saved_remove.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    saved_remove.add_argument("name", help="Saved search name")

    saved_run = saved_subparsers.add_parser("run", help="Run a saved search", add_help=False)
    saved_run.add_argument("-help", "--help", action="help", help="Show this help message and exit")
    saved_run.add_argument("-version", "--version", action="version", version=f"%(prog)s {__version__}")
    saved_run.add_argument("name", help="Saved search name")
    _add_display_args(saved_run, include_exports=False)

    return parser


def _add_saved_search_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--skill", dest="skills", action="append", default=[], help="Required skill. Repeat to add more.")
    parser.add_argument("--exclude", action="append", default=[], help="Term to exclude from results.")
    parser.add_argument("--company", action="append", default=[], help="Company to prefer or require. Repeat to add more.")
    parser.add_argument("--remote", action="store_true", help="Remote/WFH jobs only")
    parser.add_argument("--fresher", action="store_true", help="Fresher-friendly roles only")


def _add_saved_search_display_prefs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--show-score", action="store_true", help="Save score display preference")
    parser.add_argument("--explain-score", action="store_true", help="Save score explanation preference")
    parser.add_argument("--show-salary", action="store_true", help="Save salary display preference")
    parser.add_argument("--show-skills", action="store_true", help="Save skills display preference")
    parser.add_argument("--verbose", action="store_true", help="Save verbose display preference")


def _add_display_args(parser: argparse.ArgumentParser, *, include_exports: bool = True) -> None:
    if include_exports:
        parser.add_argument("--csv", default="", metavar="FILE", help="Export user-friendly flattened CSV")
        parser.add_argument("--csv-full", default="", metavar="FILE", help="Export full raw-schema CSV")
        parser.add_argument("--json", default="", metavar="FILE", help="Export user-friendly flattened JSON")
        parser.add_argument("--json-full", default="", metavar="FILE", help="Export full raw-schema JSON")
    parser.add_argument("--output", choices=["text", "json", "json-full"], default="text", help="Write results to stdout")
    parser.add_argument("--json-stdout", action="store_true", help="Alias for --output json")
    parser.add_argument("--summary-json", action="store_true", help="Write search summary envelope to stdout")
    parser.add_argument("--no-pretty", action="store_true", help="Disable human-formatted output and emit machine-readable JSON")
    parser.add_argument("--top", type=int, default=25, help="Max rows to display")
    parser.add_argument("--verbose", action="store_true", help="Show expanded per-job detail")
    parser.add_argument("--show-score", action="store_true", help="Show match score in search results")
    parser.add_argument("--explain-score", action="store_true", help="Show ranking reasons and warnings")
    parser.add_argument("--show-salary", action="store_true", help="Show salary or stipend when available")
    parser.add_argument("--show-skills", action="store_true", help="Show skills when available")


def _add_query_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("role", help="Role or search term")
    parser.add_argument(
        "--source",
        "--site",
        dest="sources",
        action="append",
        metavar="SOURCE",
        help="Source to use. Repeat to add more.",
    )
    parser.add_argument("--city", default="", metavar="CITY", help="City to filter by")
    parser.add_argument("--country", default="", help="Country")
    parser.add_argument("--location", default="", help="Free-form location")
    parser.add_argument("--source-family", default="", help="Expand to every source in a source family")
    parser.add_argument(
        "--job-kind",
        choices=["job", "internship", "hackathon", "competition", "fellowship"],
        default="",
        help="Filter by normalized job kind",
    )
    parser.add_argument(
        "--work-mode",
        choices=["remote", "hybrid", "onsite", "unknown"],
        default="",
        help="Filter by normalized work mode",
    )
    parser.add_argument(
        "--match-mode",
        choices=["strict", "balanced", "broad"],
        default="balanced",
        help="Title/query matching strictness",
    )
    parser.add_argument("--strict-match", action="store_true", help="Alias for --match-mode strict")
    parser.add_argument("--related", action="store_true", help="Alias for --match-mode broad")
    parser.add_argument("--min-exp", type=float, default=None, help="Minimum experience in years")
    parser.add_argument("--max-exp", type=float, default=None, help="Maximum experience in years")
    parser.add_argument("--salary-min", type=float, default=None, help="Minimum salary")
    parser.add_argument("--posted-days", type=int, default=None, help="Only include jobs from the last N days")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max results per source; use 0 to fetch until the source is exhausted",
    )
    parser.add_argument(
        "--dedupe-mode",
        choices=["strict", "heuristic", "fuzzy", "none"],
        default="strict",
        help="Cross-source deduplication policy",
    )
    parser.add_argument(
        "--dedupe-scope",
        choices=["title-company-location", "title-company-location-country", "title-company"],
        default="title-company-location-country",
        help="Fields used for heuristic/fuzzy dedupe identity",
    )
    parser.add_argument("--fuzzy-dedupe", action="store_true", help="Alias for --dedupe-mode fuzzy")
    parser.add_argument("--cache", action="store_true", help="Use and update response cache")
    parser.add_argument("--cache-dir", default=".jobhunter_cache", help="Cache directory")
    if parser.prog.endswith("search"):
        _add_saved_search_fields(parser)


def _add_health_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when health thresholds fail")
    parser.add_argument("--min-parsed", type=int, default=1, help="Minimum parsed items per source")
    parser.add_argument("--max-failures", type=int, default=0, help="Maximum failing sources allowed")
    parser.add_argument("--min-jobs-per-second", type=float, default=0.0, help="Minimum benchmark throughput")
    parser.add_argument("--max-requests", type=int, default=0, help="Maximum requests allowed per source benchmark")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    argv = argv or sys.argv[1:]
    machine_output = _wants_machine_output(argv)
    try:
        args = parser.parse_args(argv)
    except CliUsageError as exc:
        if machine_output:
            print(json.dumps(_error_envelope("usage_error", str(exc), exit_code=EXIT_USAGE_ERROR), ensure_ascii=False, indent=2))
        else:
            parser.print_usage(sys.stderr)
            print(f"hirehunt: error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    if args.command == "saved-search":
        return _handle_saved_search(args)

    thresholds = HealthThresholds(
        min_parsed=args.min_parsed if hasattr(args, "min_parsed") else 1,
        max_failures=args.max_failures if hasattr(args, "max_failures") else 0,
        min_jobs_per_second=args.min_jobs_per_second if hasattr(args, "min_jobs_per_second") else 0.0,
        max_requests=args.max_requests if hasattr(args, "max_requests") else 0,
    )

    if args.command == "search":
        result = _run_search_from_args(args)
        return _handle_search_output(result, args)

    if args.command == "validate":
        query = _query_from_args(args)
        results = validate_sources(query, args.sources)
        _print_validation(results)
        if args.report:
            write_validation_report(results, args.report)
        issues = evaluate_validation_health(results, thresholds)
        _print_health_issues(issues)
        return EXIT_HEALTH_FAILURE if args.strict and issues else EXIT_OK

    if args.command == "benchmark":
        query = _query_from_args(args)
        results = benchmark_sources(query, args.sources)
        _print_benchmark(results)
        if args.report:
            write_benchmark_report(results, args.report)
        issues = evaluate_benchmark_health(results, thresholds)
        _print_health_issues(issues)
        return EXIT_HEALTH_FAILURE if args.strict and issues else EXIT_OK

    print(json.dumps(_error_envelope("usage_error", f"unknown command: {args.command}", exit_code=EXIT_USAGE_ERROR), ensure_ascii=False, indent=2))
    return EXIT_USAGE_ERROR


def _run_search_from_args(args):
    query = _query_from_args(args)
    return search_jobs(
        search_term=query.search_term,
        sources=query.sources,
        city=query.city,
        country=query.country,
        location=query.location,
        companies=getattr(args, "company", []),
        skills=getattr(args, "skills", []),
        exclude=getattr(args, "exclude", []),
        source_family=query.source_family,
        job_kind=query.job_kind,
        remote=getattr(args, "remote", None) or None,
        work_mode=query.work_mode,
        fresher=getattr(args, "fresher", None) or None,
        experience_min=query.experience_min,
        experience_max=query.experience_max,
        salary_min=query.salary_min,
        posted_within_days=query.posted_within_days,
        results_wanted=query.results_wanted,
        dedupe_mode=query.dedupe_mode,
        dedupe_scope=query.dedupe_scope,
        match_mode=query.match_mode,
        cache_enabled=query.cache_enabled,
        cache_dir=query.cache_dir,
    )


def _query_from_args(args) -> JobQuery:
    match_mode = args.match_mode
    if getattr(args, "strict_match", False):
        match_mode = "strict"
    elif getattr(args, "related", False):
        match_mode = "broad"
    dedupe_mode = "fuzzy" if getattr(args, "fuzzy_dedupe", False) else args.dedupe_mode
    return JobQuery(
        role=args.role,
        search_term=args.role,
        sources=args.sources or "auto",
        city=args.city,
        country=args.country,
        location=args.location,
        source_family=args.source_family,
        job_kind=args.job_kind or None,
        work_mode=args.work_mode or None,
        experience_min=args.min_exp,
        experience_max=args.max_exp,
        salary_min=args.salary_min,
        posted_within_days=args.posted_days,
        results_wanted=args.limit,
        dedupe_mode=dedupe_mode,
        dedupe_scope=args.dedupe_scope,
        match_mode=match_mode,
        cache_enabled=args.cache,
        cache_dir=args.cache_dir,
    )


def _handle_search_output(result, args) -> int:
    exit_code = _search_exit_code(result)
    try:
        if getattr(args, "csv", ""):
            to_csv(result.jobs, args.csv)
        if getattr(args, "csv_full", ""):
            to_csv(result.jobs, args.csv_full, full=True)
        if getattr(args, "json", ""):
            to_json(result.jobs, args.json)
        if getattr(args, "json_full", ""):
            to_json(result.jobs, args.json_full, full=True)

        output_mode = _effective_output_mode(args)
        if output_mode == "text":
            _print_search(result, args.top, args)
        elif output_mode == "summary-json":
            print(json.dumps(_summary_envelope(result, args, exit_code=exit_code), ensure_ascii=False, indent=2))
        else:
            full = output_mode == "json-full"
            print(json.dumps(_result_envelope(result, args, exit_code=exit_code, full=full), ensure_ascii=False, indent=2))
    except OSError as exc:
        print(json.dumps(_error_envelope("output_error", str(exc), exit_code=EXIT_OUTPUT_ERROR), ensure_ascii=False, indent=2))
        return EXIT_OUTPUT_ERROR
    return exit_code


def _effective_output_mode(args) -> str:
    if getattr(args, "summary_json", False):
        return "summary-json"
    if getattr(args, "json_stdout", False):
        return "json"
    if getattr(args, "no_pretty", False) and args.output == "text":
        return "json"
    return args.output


def _search_exit_code(result) -> int:
    if getattr(result, "partial", False) or getattr(result, "errors", {}):
        return EXIT_PARTIAL_RESULTS
    if not getattr(result, "jobs", []):
        return EXIT_NO_JOBS
    return EXIT_OK


def _search_status(result) -> str:
    code = _search_exit_code(result)
    return {
        EXIT_OK: "ok",
        EXIT_NO_JOBS: "no_jobs",
        EXIT_PARTIAL_RESULTS: "partial",
    }.get(code, "error")


def _handle_saved_search(args) -> int:
    store = Path(args.file)
    searches = _load_saved_searches(store)
    if args.saved_command == "list":
        if getattr(args, "json", False):
            print(json.dumps(searches, ensure_ascii=False, indent=2))
            return EXIT_OK
        if not searches:
            print("No saved searches")
            return EXIT_OK
        for name, item in sorted(searches.items()):
            print(f"- {name}: {item.get('role', '')}")
        return EXIT_OK
    if args.saved_command == "show":
        saved = searches.get(args.name)
        if saved is None:
            print(json.dumps(_error_envelope("saved_search_not_found", args.name, exit_code=EXIT_USAGE_ERROR), ensure_ascii=False, indent=2))
            return EXIT_USAGE_ERROR
        print(json.dumps(saved, ensure_ascii=False, indent=2))
        return EXIT_OK
    if args.saved_command == "remove":
        if args.name not in searches:
            print(json.dumps(_error_envelope("saved_search_not_found", args.name, exit_code=EXIT_USAGE_ERROR), ensure_ascii=False, indent=2))
            return EXIT_USAGE_ERROR
        searches.pop(args.name)
        _write_saved_searches(store, searches)
        print(f"Removed saved search '{args.name}'")
        return EXIT_OK
    if args.saved_command == "add":
        query = _query_from_args(args)
        searches[args.name] = {
            "role": args.role,
            "sources": args.sources or "auto",
            "city": args.city,
            "country": args.country,
            "location": args.location,
            "source_family": args.source_family,
            "job_kind": args.job_kind or None,
            "work_mode": args.work_mode or None,
            "match_mode": query.match_mode,
            "min_exp": args.min_exp,
            "max_exp": args.max_exp,
            "salary_min": args.salary_min,
            "posted_days": args.posted_days,
            "limit": args.limit,
            "dedupe_mode": query.dedupe_mode,
            "dedupe_scope": args.dedupe_scope,
            "skills": args.skills,
            "exclude": args.exclude,
            "company": args.company,
            "remote": args.remote,
            "fresher": args.fresher,
            "show_score": args.show_score,
            "explain_score": args.explain_score,
            "show_salary": args.show_salary,
            "show_skills": args.show_skills,
            "verbose": args.verbose,
        }
        _write_saved_searches(store, searches)
        print(f"Saved search '{args.name}'")
        return EXIT_OK
    if args.saved_command == "run":
        saved = searches.get(args.name)
        if saved is None:
            print(json.dumps(_error_envelope("saved_search_not_found", args.name, exit_code=EXIT_USAGE_ERROR), ensure_ascii=False, indent=2))
            return EXIT_USAGE_ERROR
        saved_args = argparse.Namespace(
            role=saved["role"],
            sources=saved.get("sources") or "auto",
            city=saved.get("city", ""),
            country=saved.get("country", ""),
            location=saved.get("location", ""),
            source_family=saved.get("source_family", ""),
            job_kind=saved.get("job_kind") or "",
            work_mode=saved.get("work_mode") or "",
            match_mode=saved.get("match_mode", "balanced"),
            strict_match=False,
            related=False,
            min_exp=saved.get("min_exp"),
            max_exp=saved.get("max_exp"),
            salary_min=saved.get("salary_min"),
            posted_days=saved.get("posted_days"),
            limit=saved.get("limit", 20),
            dedupe_mode=saved.get("dedupe_mode", "strict"),
            dedupe_scope=saved.get("dedupe_scope", "title-company-location-country"),
            fuzzy_dedupe=saved.get("dedupe_mode") == "fuzzy",
            company=saved.get("company", []),
            skills=saved.get("skills", []),
            exclude=saved.get("exclude", []),
            remote=saved.get("remote", False),
            fresher=saved.get("fresher", False),
            cache=False,
            cache_dir=".jobhunter_cache",
            csv="",
            csv_full="",
            json="",
            json_full="",
            output=args.output,
            json_stdout=args.json_stdout,
            summary_json=args.summary_json,
            no_pretty=args.no_pretty,
            top=args.top,
            verbose=saved.get("verbose", False),
            show_score=saved.get("show_score", False),
            explain_score=saved.get("explain_score", False),
            show_salary=saved.get("show_salary", False),
            show_skills=saved.get("show_skills", False),
        )
        result = _run_search_from_args(saved_args)
        return _handle_search_output(result, saved_args)
    return EXIT_USAGE_ERROR


def _load_saved_searches(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_saved_searches(path: Path, searches: dict[str, dict]) -> None:
    path.write_text(json.dumps(searches, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_search(result, top: int, args) -> None:
    print(f"Found {len(result.jobs)} jobs")
    print()
    for index, job in enumerate(result.jobs[:top], start=1):
        _print_job(job, index, args)
        print()
    _print_summary(result)
    warnings = list(getattr(result, "warnings", []))
    if warnings:
        print()
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    errors = dict(getattr(result, "errors", {}))
    if errors:
        print()
        print("Errors:")
        for source, error in sorted(errors.items()):
            print(f"- {source}: {error}")


def _print_job(job: Job, index: int, args) -> None:
    header = f"{index}. {job.title} @ {job.company}"
    if args.show_score and not args.explain_score:
        header += f" [{job.match_score:.0f}]"
    print(header)
    print(f"   {_icon('📍', 'Loc:')} {_format_location(job)}")
    exp_line = _format_experience(job)
    if exp_line:
        print(f"   {_icon('💼', 'Exp:')} {exp_line}")
    print(f"   {_icon('🕒', 'Posted:')} {_format_posted_age(job)}")

    compensation = _format_compensation(job)
    if compensation and (args.show_salary or True):
        print(f"   {_icon('💰', 'Salary:')} {compensation}")
    if job.company_industry:
        print(f"   {_icon('🏢', 'Industry:')} {job.company_industry}")
    if job.company_rating:
        print(f"   {_icon('⭐', 'Rating:')} {job.company_rating}")

    if args.verbose:
        if job.employment_type:
            print(f"   {_icon('🧾', 'Type:')} {job.employment_type}")
        if job.skills and args.show_skills:
            print(f"   {_icon('🛠️', 'Skills:')} {', '.join(job.skills[:8])}")
        print(f"   {_icon('🔎', 'Source:')} {job.source.title()}")
        print(f"   {_icon('🔗', 'Link:')} {job.job_url}")
    else:
        print(f"   {_icon('🔎', 'Source:')} {job.source.title()}")
        if args.show_skills and job.skills:
            print(f"   {_icon('🛠️', 'Skills:')} {', '.join(job.skills[:8])}")

    if args.explain_score:
        print(f"   {_icon('📊', 'Score:')} {job.match_score:.0f}")
        print("   Signals:")
        reasons = list(job.reasons[:6]) or ["no ranking signals recorded"]
        for reason in reasons:
            print(f"   + {reason}")
        if job.warnings:
            print("   Caveats:")
            for warning in job.warnings[:3]:
                print(f"   - {warning}")


def _print_summary(result) -> None:
    summary = _summary_envelope(result, None)
    print("Sources:")
    for source, stats in summary["source_summary"].items():
        print(
            f"- {source.title()}: {stats['kept'] or stats['parsed']} kept | {stats['parsed']} parsed | "
            f"{stats['duplicates']} dup | {stats['filtered_out']} filtered | {stats['completion']}"
        )
        reasons = stats["filter_reasons"]
        if reasons:
            for key, value in sorted(reasons.items()):
                print(f"  - {key}: {value}")
    totals = summary["totals"]
    if totals["duplicates_removed"] or totals["filtered_out"]:
        print("Filtered:")
        if totals["duplicates_removed"]:
            print(f"- duplicates removed: {totals['duplicates_removed']}")
        if totals["filtered_out"]:
            print(f"- filtered out: {totals['filtered_out']}")
    if summary["filter_reasons"]:
        print("Combined filter reasons:")
        for key, value in sorted(summary["filter_reasons"].items()):
            print(f"- {key}: {value}")


def _print_validation(results) -> None:
    print("HireHunt live validation")
    print("source | ok | status | backend | parsed | samples | error")
    print("-" * 90)
    for item in results:
        samples = "; ".join(item.sample_titles[:2])
        ok = "yes" if item.ok else "no"
        print(
            f"{item.source} | {ok} | {item.status_code} | {item.backend or '-'} | "
            f"{item.parsed_count} | {samples} | {item.error}"
        )


def _print_benchmark(results) -> None:
    print("HireHunt source benchmark")
    print("source | seconds | requests | parsed | jobs/s | completion | error")
    print("-" * 90)
    for item in results:
        print(
            f"{item.source} | {item.duration_seconds:.2f} | {item.requests} | "
            f"{item.parsed_count} | {item.jobs_per_second:.2f} | "
            f"{item.completion} | {item.error}"
        )


def _print_health_issues(issues) -> None:
    if not issues:
        return
    print("Health issues:")
    for issue in issues:
        print(f"{issue.source} | {issue.code} | {issue.message}")


def _summary_envelope(result, args=None, *, exit_code: int | None = None) -> dict[str, object]:
    combined_reasons: dict[str, int] = {}
    sources: dict[str, dict[str, object]] = {}
    for source, stats in sorted(getattr(result, "stats", {}).items()):
        item = {
            "kept": getattr(stats, "kept", 0),
            "parsed": getattr(stats, "parsed", 0),
            "duplicates": getattr(stats, "duplicates", 0),
            "filtered_out": getattr(stats, "filtered_out", 0),
            "requests": getattr(stats, "requests", 0),
            "completion": str(getattr(stats, "completion", "unknown")),
            "completion_reason": getattr(stats, "completion_reason", ""),
            "filter_reasons": dict(getattr(stats, "filter_reasons", {})),
        }
        sources[source] = item
        for key, value in item["filter_reasons"].items():
            combined_reasons[key] = combined_reasons.get(key, 0) + value

    duplicates = sum(item["duplicates"] for item in sources.values())
    filtered = sum(item["filtered_out"] for item in sources.values())
    resolved_exit = exit_code if exit_code is not None else _search_exit_code(result)
    return {
        "ok": resolved_exit == EXIT_OK,
        "status": _search_status(result),
        "exit_code": resolved_exit,
        "job_count": len(getattr(result, "jobs", [])),
        "partial": getattr(result, "partial", False),
        "selected_sources": list(getattr(result, "selected_sources", [])),
        "warnings": list(getattr(result, "warnings", [])),
        "errors": dict(getattr(result, "errors", {})),
        "totals": {
            "duplicates_removed": duplicates,
            "filtered_out": filtered,
        },
        "source_summary": sources,
        "filter_reasons": combined_reasons,
        "query": _query_snapshot(args) if args is not None else None,
    }


def _result_envelope(result, args, *, exit_code: int, full: bool) -> dict[str, object]:
    jobs = [job.to_dict() if full else _flat_job_dict(job) for job in result.jobs]
    return {
        "ok": exit_code == EXIT_OK,
        "status": _search_status(result),
        "exit_code": exit_code,
        "command": "search",
        "version": __version__,
        "meta": {
            "format": "json-full" if full else "json",
            "schema_version": result.schema_version,
        },
        "query": _query_snapshot(args),
        "summary": _summary_envelope(result, args, exit_code=exit_code),
        "jobs": jobs,
    }


def _query_snapshot(args) -> dict[str, object]:
    return {
        "role": args.role,
        "sources": args.sources if isinstance(args.sources, list) else args.sources or "auto",
        "city": args.city,
        "country": args.country,
        "location": args.location,
        "source_family": args.source_family,
        "job_kind": args.job_kind or None,
        "work_mode": args.work_mode or None,
        "match_mode": "strict" if getattr(args, "strict_match", False) else "broad" if getattr(args, "related", False) else args.match_mode,
        "dedupe_mode": "fuzzy" if getattr(args, "fuzzy_dedupe", False) else args.dedupe_mode,
        "dedupe_scope": args.dedupe_scope,
        "min_exp": args.min_exp,
        "max_exp": args.max_exp,
        "salary_min": args.salary_min,
        "posted_days": args.posted_days,
        "limit": args.limit,
        "skills": getattr(args, "skills", []),
        "exclude": getattr(args, "exclude", []),
        "company": getattr(args, "company", []),
        "remote": getattr(args, "remote", False),
        "fresher": getattr(args, "fresher", False),
    }


def _flat_job_dict(job: Job) -> dict[str, object]:
    from hirehunt.exporters.csv import _job_to_flat_dict

    return _job_to_flat_dict(job)


def _error_envelope(code: str, message: str, *, exit_code: int = EXIT_OUTPUT_ERROR) -> dict[str, object]:
    return {
        "ok": False,
        "status": "error",
        "exit_code": exit_code,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _format_location(job: Job) -> str:
    return job.display_location()


def _format_experience(job: Job) -> str:
    return job.display_experience()


def _format_posted_age(job: Job) -> str:
    return job.display_posted_age()


def _format_compensation(job: Job) -> str:
    return job.display_compensation()


def _icon(emoji: str, fallback: str) -> str:
    encoding = getattr(sys.stdout, "encoding", "") or ""
    try:
        emoji.encode(encoding or "utf-8")
        return emoji
    except UnicodeEncodeError:
        return fallback


def _wants_machine_output(argv: list[str]) -> bool:
    for index, item in enumerate(argv):
        if item in {"--json-stdout", "--summary-json", "--no-pretty"}:
            return True
        if item == "--output" and index + 1 < len(argv) and argv[index + 1] in {"json", "json-full"}:
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
