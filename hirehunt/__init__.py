"""JobHunter public API."""

from hirehunt.engine import SearchEngine, scrape_jobs, search_jobs, search_jobs_async
from hirehunt.models import Job, JobKind, Money, SalaryPeriod, ScrapeResult, WorkMode
from hirehunt.query import JobProfile, JobQuery

__all__ = [
    "Job",
    "JobKind",
    "JobQuery",
    "JobProfile",
    "Money",
    "SalaryPeriod",
    "ScrapeResult",
    "SearchEngine",
    "WorkMode",
    "scrape_jobs",
    "search_jobs",
    "search_jobs_async",
]
