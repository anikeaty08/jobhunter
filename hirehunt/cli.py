"""Command line interface — rich, beautiful output."""

from __future__ import annotations

import argparse
import sys

from hirehunt.engine import search_jobs
from hirehunt.exporters.csv import to_csv
from hirehunt.exporters.json import to_json
from hirehunt.query import JobQuery

# ── Source metadata for badges ────────────────────────────────────────────────
_SOURCE_BADGE: dict[str, str] = {
    "naukri":        "🇮🇳 naukri",
    "shine":         "🇮🇳 shine",
    "internshala":   "🇮🇳 internshala",
    "unstop":        "🇮🇳 unstop",
    "linkedin":      "🌍 linkedin",
    "indeed":        "🌍 indeed",
    "google_careers":"⚡ google",
    "amazon":        "⚡ amazon",
    "meta":          "⚡ meta",
    "netflix":       "⚡ netflix",
    "microsoft":     "⚡ microsoft",
    "apple":         "⚡ apple",
}

_SOURCE_COLOR: dict[str, str] = {
    "naukri":        "cyan",
    "shine":         "bright_cyan",
    "internshala":   "bright_blue",
    "unstop":        "blue",
    "linkedin":      "steel_blue1",
    "indeed":        "medium_purple1",
    "google_careers":"bright_green",
    "amazon":        "orange1",
    "meta":          "bright_blue",
    "netflix":       "red1",
    "microsoft":     "dodger_blue1",
    "apple":         "grey84",
}


def _salary_str(job) -> str:
    m = job.salary if job.salary and job.salary.has_value else None
    s = job.stipend if job.stipend and job.stipend.has_value else None
    money = m or s
    if not money:
        return "—"
    if money.min_amount and money.max_amount and money.min_amount != money.max_amount:
        lo = _fmt_amount(money.min_amount, money.currency)
        hi = _fmt_amount(money.max_amount, money.currency)
        return f"{lo}–{hi}"
    amt = _fmt_amount(money.min_amount or money.max_amount, money.currency)
    period = f"/{money.period}" if money.period and money.period != "unknown" else ""
    return f"{amt}{period}"


def _fmt_amount(amount: float | None, currency: str) -> str:
    if amount is None:
        return "?"
    if currency == "INR":
        if amount >= 100_000:
            return f"₹{amount/100_000:.1f}L"
        if amount >= 1_000:
            return f"₹{amount/1_000:.0f}K"
        return f"₹{amount:.0f}"
    if currency == "USD":
        if amount >= 1_000:
            return f"${amount/1_000:.0f}K"
        return f"${amount:.0f}"
    return f"{amount:.0f} {currency}"


def _score_bar(score: float, width: int = 8) -> str:
    filled = int(round(score / 100 * width))
    return "█" * filled + "░" * (width - filled)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hirehunt",
        description="🎯 HireHunt — Search jobs across 12 India & global sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hirehunt search "python developer" --city blr
  hirehunt search "data analyst" --city mumbai --source naukri --source shine
  hirehunt search "software engineer" --source google_careers --source amazon
  hirehunt search "python intern" --city del --source internshala --csv out.csv
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search jobs across sources")
    search.add_argument("role", help="Role or search term (e.g. 'python developer')")
    search.add_argument("--source", "--site", dest="sources", action="append",
                        metavar="SOURCE",
                        help="Source(s) to search. Repeat to add more. "
                             "Options: naukri, shine, internshala, unstop, linkedin, indeed, "
                             "google_careers, amazon, meta, netflix, microsoft, apple")
    search.add_argument("--city", default="", metavar="CITY",
                        help="City to filter by. Supports aliases: blr, mum, del, hyd, chn, kol, etc.")
    search.add_argument("--country", default="", help="Country (e.g. India)")
    search.add_argument("--skill", dest="skills", action="append", default=[],
                        help="Required skill. Repeat to add more.")
    search.add_argument("--exclude", action="append", default=[],
                        help="Term to exclude from results.")
    search.add_argument("--remote", action="store_true", help="Remote/WFH jobs only")
    search.add_argument("--fresher", action="store_true", help="Fresher-friendly roles only")
    search.add_argument("--limit", type=int, default=20,
                        help="Max results per source (default: 20)")
    search.add_argument("--csv", default="", metavar="FILE", help="Export to CSV")
    search.add_argument("--json", default="", metavar="FILE", help="Export to JSON")
    search.add_argument("--no-color", action="store_true", help="Disable colored output")
    search.add_argument("--top", type=int, default=25, help="Max rows to display (default: 25)")
    return parser


def _print_rich(result, query_city: str, role: str, top: int, no_color: bool, csv_path: str, json_path: str) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        from rich import box
        console = Console(no_color=no_color, highlight=False)
        USE_RICH = True
    except ImportError:
        USE_RICH = False

    jobs = result.jobs

    if not USE_RICH:
        # Fallback plain output
        print(f"\n{'='*70}")
        print(f"  HireHunt: {len(jobs)} jobs for '{role}'" + (f" in {query_city}" if query_city else ""))
        print(f"{'='*70}\n")
        for w in result.warnings:
            print(f"  {w}")
        if result.warnings:
            print()
        for i, job in enumerate(jobs[:top], 1):
            sal = _salary_str(job)
            print(f"  [{i}] {job.title} @ {job.company}")
            print(f"       {job.city or 'N/A'} | {_SOURCE_BADGE.get(job.source, job.source)} | {sal}")
            print(f"       {job.job_url[:80]}")
            print()
        _export(result, csv_path, json_path)
        return

    # ── Header ──────────────────────────────────────────────────────────────
    loc_part = f" in {query_city}" if query_city else ""
    header = Text()
    header.append("🎯 HireHunt", style="bold white")
    header.append("  ·  ", style="dim")
    header.append(f"'{role}'", style="bold cyan")
    if query_city:
        header.append(" in ", style="dim")
        header.append(query_city, style="bold yellow")
    header.append("  ·  ", style="dim")
    header.append(f"{len(jobs)} unique jobs", style="bold green")
    console.print()
    console.print(Panel(header, border_style="bright_blue", padding=(0, 2)))

    # ── Warnings panel ──────────────────────────────────────────────────────
    if result.warnings:
        warn_text = "\n".join(result.warnings)
        console.print(Panel(warn_text, title="Notices", border_style="yellow", padding=(0, 1)))

    # ── Source stats bar ────────────────────────────────────────────────────
    console.print()
    stats_parts = []
    for src, s in sorted(result.stats.items()):
        color = _SOURCE_COLOR.get(src, "white")
        badge = _SOURCE_BADGE.get(src, src)
        stats_parts.append(f"[{color}]{badge}[/] [dim]{s.found}↓ {s.kept}✓[/]")
    console.print("  " + "   ".join(stats_parts))
    console.print()

    # ── Main table ──────────────────────────────────────────────────────────
    table = Table(
        show_header=True,
        header_style="bold white on grey23",
        box=box.ROUNDED,
        border_style="bright_blue",
        row_styles=["", "dim"],
        show_lines=False,
        expand=False,
    )
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Match", width=10)
    table.add_column("Title", min_width=30, max_width=45, no_wrap=True)
    table.add_column("Company", min_width=18, max_width=26, no_wrap=True)
    table.add_column("City", width=14, no_wrap=True)
    table.add_column("Source", width=16)
    table.add_column("Salary", width=14, style="bold green")
    table.add_column("URL", min_width=40, no_wrap=True, style="bright_blue")

    for i, job in enumerate(jobs[:top], 1):
        score_bar = _score_bar(job.match_score)
        score_color = "green" if job.match_score >= 60 else "yellow" if job.match_score >= 30 else "red"
        score_str = f"[{score_color}]{score_bar}[/] [dim]{job.match_score:.0f}[/]"

        src_color = _SOURCE_COLOR.get(job.source, "white")
        src_badge = _SOURCE_BADGE.get(job.source, job.source)
        src_str = f"[{src_color}]{src_badge}[/]"

        salary = _salary_str(job)
        sal_str = f"[bold green]{salary}[/]" if salary != "—" else "[dim]—[/]"

        city = job.city or "—"
        kind_icon = {"internship": "📚", "hackathon": "🏆", "job": "💼", "fellowship": "🎓"}.get(str(job.job_kind), "")
        title_str = f"{kind_icon} {job.title}" if kind_icon else job.title

        table.add_row(
            str(i),
            score_str,
            title_str,
            job.company,
            city,
            src_str,
            sal_str,
            job.job_url,
        )

    console.print(table)

    # ── Footer ──────────────────────────────────────────────────────────────
    dedup_count = sum(s.duplicates for s in result.stats.values())
    console.print(
        f"\n  [dim]Scraped from {len(result.stats)} sources · "
        f"{dedup_count} duplicates removed · "
        f"Showing top {min(top, len(jobs))} of {len(jobs)}[/]"
    )
    if result.errors:
        for src, err in result.errors.items():
            console.print(f"  [red]✗ {src}: {err[:60]}[/]")
    console.print()

    _export(result, csv_path, json_path, console)


def _export(result, csv_path: str, json_path: str, console=None) -> None:
    if csv_path:
        to_csv(result.jobs, csv_path)
        msg = f"  ✅ CSV saved → {csv_path}"
        if console:
            console.print(f"[green]{msg}[/]")
        else:
            print(msg)
    if json_path:
        to_json(result.jobs, json_path)
        msg = f"  ✅ JSON saved → {json_path}"
        if console:
            console.print(f"[green]{msg}[/]")
        else:
            print(msg)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "search":
        result = search_jobs(
            search_term=args.role,
            sources=args.sources or "auto",
            city=args.city,
            country=args.country,
            skills=args.skills,
            exclude=args.exclude,
            remote=args.remote or None,
            fresher=args.fresher or None,
            results_wanted=args.limit,
        )
        _print_rich(
            result,
            query_city=result.jobs[0].city if result.jobs else args.city,
            role=args.role,
            top=args.top,
            no_color=args.no_color,
            csv_path=args.csv,
            json_path=args.json,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
