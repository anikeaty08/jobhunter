"""Core data models for normalized job search results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, ClassVar
import json

JOB_SCHEMA_VERSION = "1.0"


class JobKind(StrEnum):
    JOB = "job"
    INTERNSHIP = "internship"
    HACKATHON = "hackathon"
    COMPETITION = "competition"
    FELLOWSHIP = "fellowship"
    UNKNOWN = "unknown"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class SalaryPeriod(StrEnum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    PROJECT = "project"
    UNKNOWN = "unknown"


class CompletionStatus(StrEnum):
    EXHAUSTED = "exhausted"
    CAPPED = "capped"
    PARTIAL = "partial"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourceCapabilities:
    countries: tuple[str, ...] = ()
    job_kinds: tuple[JobKind, ...] = (JobKind.JOB,)
    supported_filters: frozenset[str] = frozenset()
    pagination: bool = False
    exhaustive_search: bool = False
    description: str = ""


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    family: str = "custom"
    adapter: str = ""
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    config: dict[str, Any] = field(default_factory=dict)
    capabilities: SourceCapabilities = field(default_factory=SourceCapabilities)


@dataclass(frozen=True)
class Money:
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str = "INR"
    period: SalaryPeriod = SalaryPeriod.UNKNOWN
    raw_text: str = ""

    @property
    def has_value(self) -> bool:
        return self.min_amount is not None or self.max_amount is not None


@dataclass
class Job:
    schema_version: ClassVar[str] = JOB_SCHEMA_VERSION

    title: str
    company: str
    source: str
    job_url: str

    location: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    work_mode: WorkMode = WorkMode.UNKNOWN

    job_kind: JobKind = JobKind.UNKNOWN
    employment_type: str = ""
    experience_min: float | None = None
    experience_max: float | None = None
    experience_text: str = ""

    salary: Money = field(default_factory=Money)
    stipend: Money = field(default_factory=Money)

    skills: list[str] = field(default_factory=list)
    description: str = ""
    date_posted: str | None = None
    deadline: str | None = None

    company_url: str = ""
    company_rating: str = ""
    company_industry: str = ""

    source_job_id: str = ""
    apply_url: str = ""
    easy_apply: bool = False

    match_score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        from hirehunt.utils.normalization import (
            clean_text,
            extract_primary_city,
            normalize_company,
            normalize_city,
            normalize_country,
            normalize_location_text,
            normalize_skills,
            normalize_url,
            parse_date,
            parse_work_mode,
        )
        if isinstance(self.salary, dict):
            self.salary = Money(**self.salary)
        if isinstance(self.stipend, dict):
            self.stipend = Money(**self.stipend)
        if isinstance(self.salary.period, str):
            self.salary = Money(
                min_amount=self.salary.min_amount,
                max_amount=self.salary.max_amount,
                currency=self.salary.currency,
                period=SalaryPeriod(self.salary.period),
                raw_text=self.salary.raw_text,
            )
        if isinstance(self.stipend.period, str):
            self.stipend = Money(
                min_amount=self.stipend.min_amount,
                max_amount=self.stipend.max_amount,
                currency=self.stipend.currency,
                period=SalaryPeriod(self.stipend.period),
                raw_text=self.stipend.raw_text,
            )

        raw_location = self.location
        raw_employment_type = self.employment_type
        raw_description = self.description
        self.title = clean_text(self.title)
        self.company = normalize_company(self.company)
        self.job_url = normalize_url(self.job_url)
        self.apply_url = normalize_url(self.apply_url)
        self.company_url = normalize_url(self.company_url)
        self.location = normalize_location_text(self.location)
        self.city = normalize_city(clean_text(self.city).strip(" -|,"))
        if self.city.lower() in {"hybrid", "hybrid -", "onsite", "onsite -", "remote", "remote -"}:
            self.city = ""
        if not self.city:
            self.city = extract_primary_city(self.location)
        if self.city == "Remote":
            self.city = ""
            if self.work_mode == WorkMode.UNKNOWN:
                self.work_mode = WorkMode.REMOTE
        self.state = clean_text(self.state)
        normalized_country = normalize_country(self.country)
        self.country = normalized_country.title() if normalized_country else ""
        if self.work_mode == WorkMode.UNKNOWN:
            self.work_mode = parse_work_mode(" ".join(filter(None, [raw_location, self.location, raw_employment_type, raw_description])))
        self.employment_type = clean_text(self.employment_type)
        self.experience_text = clean_text(self.experience_text)
        self.skills = normalize_skills(self.skills)
        self.description = clean_text(self.description)
        self.date_posted = parse_date(self.date_posted)
        self.deadline = parse_date(self.deadline)
        self.company_rating = clean_text(self.company_rating)
        self.company_industry = clean_text(self.company_industry.replace("_", " ")) if self.company_industry else ""
        self.source_job_id = clean_text(self.source_job_id)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema_version"] = self.schema_version
        data["job_kind"] = str(self.job_kind)
        data["work_mode"] = str(self.work_mode)
        data["salary"]["period"] = str(self.salary.period)
        data["stipend"]["period"] = str(self.stipend.period)
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def display_location(self) -> str:
        base = self.city or self.location or self.country or "Unknown"
        if self.work_mode == WorkMode.REMOTE:
            return "Remote"
        if self.work_mode in {WorkMode.HYBRID, WorkMode.ONSITE}:
            return f"{base} ({str(self.work_mode).title()})"
        return base

    def display_experience(self) -> str:
        if self.experience_text:
            return self.experience_text
        if self.experience_min is not None and self.experience_max is not None:
            return f"{_fmt_num(self.experience_min)}-{_fmt_num(self.experience_max)} yrs"
        if self.experience_min is not None:
            return f"{_fmt_num(self.experience_min)}+ yrs"
        if self.experience_max is not None:
            return f"Up to {_fmt_num(self.experience_max)} yrs"
        return ""

    def display_posted_age(self, today: date | None = None) -> str:
        if not self.date_posted:
            return "Date unavailable"
        try:
            posted = date.fromisoformat(self.date_posted)
        except ValueError:
            return self.date_posted
        today = today or date.today()
        age = (today - posted).days
        if age <= 0:
            return "Today"
        if age == 1:
            return "1d ago"
        return f"{age}d ago"

    def display_compensation(self) -> str:
        money = self.salary if self.salary.has_value else self.stipend if self.stipend.has_value else None
        if money is None:
            return ""
        low = _fmt_money(money.min_amount)
        high = _fmt_money(money.max_amount)
        period = _format_period(str(money.period))
        if low and high:
            low_compact, low_suffix = _split_money_suffix(low)
            high_compact, high_suffix = _split_money_suffix(high)
            if low_suffix and low_suffix == high_suffix:
                shared_period = "" if low_suffix in {"LPA"} else period
                return f"{money.currency} {low_compact}-{high_compact} {low_suffix}{shared_period}".strip()
            return f"{money.currency} {low}-{high}{period}"
        if high:
            return f"{money.currency} {high}{period}"
        if low:
            return f"{money.currency} {low}{period}"
        return money.raw_text

    def to_compact_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "company": self.company,
            "source": self.source,
            "job_url": self.job_url,
            "display_location": self.display_location(),
            "experience": self.display_experience(),
            "posted": self.display_posted_age(),
            "compensation": self.display_compensation(),
            "company_rating": self.company_rating,
            "company_industry": self.company_industry,
            "match_score": self.match_score,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
        }

    def __str__(self) -> str:
        place = self.display_location()
        if place == "Unknown":
            place = "unknown location"
        return f"{self.title} @ {self.company} | {place} | {self.source} | {self.job_url}"


@dataclass
class SourceStats:
    found: int = 0
    kept: int = 0
    duplicates: int = 0
    errors: int = 0
    fetched: int = 0
    parsed: int = 0
    filtered_out: int = 0
    requests: int = 0
    completion: CompletionStatus = CompletionStatus.UNKNOWN
    completion_reason: str = ""
    filter_reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class ScrapeResult:
    jobs: list[Job] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    stats: dict[str, SourceStats] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    partial: bool = False
    selected_sources: list[str] = field(default_factory=list)
    schema_version: str = JOB_SCHEMA_VERSION

    def to_dicts(self) -> list[dict[str, Any]]:
        return [job.to_dict() for job in self.jobs]

    def to_compact_dicts(self) -> list[dict[str, Any]]:
        return [job.to_compact_dict() for job in self.jobs]

    def top(self, count: int = 20) -> list[Job]:
        return self.jobs[:count]

    def to_dataframe(self):
        from hirehunt.exporters.dataframe import to_dataframe
        return to_dataframe(self.jobs)

    def to_summary_dict(self) -> dict[str, Any]:
        source_summary: dict[str, dict[str, Any]] = {}
        combined_reasons: dict[str, int] = {}
        for source, stats in sorted(self.stats.items()):
            item = {
                "kept": stats.kept,
                "parsed": stats.parsed,
                "duplicates": stats.duplicates,
                "filtered_out": stats.filtered_out,
                "requests": stats.requests,
                "completion": str(stats.completion),
                "completion_reason": stats.completion_reason,
                "filter_reasons": dict(stats.filter_reasons),
            }
            source_summary[source] = item
            for key, value in item["filter_reasons"].items():
                combined_reasons[key] = combined_reasons.get(key, 0) + value
        return {
            "job_count": len(self.jobs),
            "partial": self.partial,
            "selected_sources": list(self.selected_sources),
            "warnings": list(self.warnings),
            "errors": dict(self.errors),
            "source_summary": source_summary,
            "filter_reasons": combined_reasons,
        }

    def to_json_envelope(self, *, query: dict[str, Any] | None = None, full: bool = False) -> dict[str, Any]:
        return {
            "ok": not self.partial and not self.errors and bool(self.jobs),
            "status": "partial" if self.partial or self.errors else "no_jobs" if not self.jobs else "ok",
            "meta": {
                "format": "json-full" if full else "json",
                "schema_version": self.schema_version,
            },
            "query": query,
            "summary": self.to_summary_dict(),
            "jobs": self.to_dicts() if full else self.to_compact_dicts(),
        }


def _fmt_num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}".rstrip("0").rstrip(".")


def _fmt_money(amount: float | None) -> str:
    if amount is None:
        return ""
    if amount >= 100000:
        value = amount / 100000
        return f"{value:.1f}".rstrip("0").rstrip(".") + " LPA"
    if amount >= 1000:
        return f"{amount:,.0f}"
    return str(int(amount) if float(amount).is_integer() else amount)


def _split_money_suffix(value: str) -> tuple[str, str]:
    parts = value.rsplit(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return value, ""


def _format_period(period: str) -> str:
    mapping = {
        "month": "/month",
        "year": "/year",
        "hour": "/hour",
        "week": "/week",
        "day": "/day",
        "project": "/project",
    }
    return mapping.get(period, "")
