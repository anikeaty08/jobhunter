"""Naukri.com scraper — uses confirmed /jobapi/v2/search REST endpoint.

Reverse engineering findings:
  - v3 returns 406, v2 returns 200 ✅
  - Requires page-load cookies first (session-based auth)
  - Required headers: appid=109, systemid=Naukri
  - Field mapping:
      title      → CONTDESIG or post (NOT 'title')
      company    → companyName
      salary     → minSal / maxSal (in LPA)
      location   → city (comma-separated)
      skills     → keywords
      experience → minExp / maxExp
      url        → urlStr or nonStaticUrlFor
      date       → addDate or dateAdded
  - Pagination: pageNo=1,2,3... with noOfResults per page
  - 15,000+ total jobs available
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from hirehunt.models import Job, JobKind, Money, SalaryPeriod, WorkMode
from hirehunt.query import JobQuery
from hirehunt.scrapers.base import BaseScraper
from hirehunt.utils.normalization import (
    clean_text,
    normalize_city,
    normalize_skills,
    parse_date,
    parse_work_mode,
)

_BASE  = "https://www.naukri.com"
_API   = f"{_BASE}/jobapi/v2/search"
_UA    = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_NAUKRI_HEADERS = {
    "appid":    "109",
    "systemid": "Naukri",
    "Accept":   "application/json",
    "User-Agent": _UA,
}
_RESULTS_PER_PAGE = 20


class NaukriScraper(BaseScraper):
    source = "naukri"
    default_country = "India"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._session: requests.Session | None = None

    def _get_session(self, keyword: str, location: str) -> requests.Session:
        """Warm up a session with Naukri cookies required by the API."""
        if self._session:
            return self._session
        sess = requests.Session()
        sess.headers.update({"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"})
        # Build a warm-up URL that mirrors what the browser would fetch
        loc_slug  = location.lower().replace(" ", "-") if location else ""
        term_slug = keyword.lower().replace(" ", "-")
        warmup = (
            f"{_BASE}/{term_slug}-jobs-in-{loc_slug}"
            if loc_slug else
            f"{_BASE}/{term_slug}-jobs"
        )
        try:
            sess.get(warmup, timeout=15)
        except Exception:
            pass
        self._session = sess
        return sess

    def search(self, query: JobQuery) -> list[Job]:
        keyword  = query.normalized_term
        location = query.city or query.location or ""
        sess = self._get_session(keyword, location)

        jobs: list[Job] = []
        page = 1

        while len(jobs) < query.results_wanted:
            params = {
                "noOfResults": _RESULTS_PER_PAGE,
                "urlType":     "search_by_keyword",
                "searchType":  "adv",
                "keyword":     keyword,
                "pageNo":      page,
            }
            if location:
                params["location"] = location
            if query.experience_min is not None:
                params["experience"] = int(query.experience_min)
            if query.salary_min:
                params["salary"] = int(query.salary_min / 100_000)  # convert to LPA

            try:
                resp = sess.get(
                    _API,
                    params=params,
                    headers=_NAUKRI_HEADERS,
                    timeout=20,
                )
            except Exception:
                break

            if resp.status_code != 200:
                break

            try:
                data = resp.json()
            except Exception:
                break

            listing = data.get("list") or []
            if not listing:
                break

            for item in listing:
                job = _parse_naukri_job(item, query)
                if job:
                    jobs.append(job)

            total_pages = data.get("totalpages", 1)
            if page >= total_pages:
                break

            page += 1
            time.sleep(0.5)   # polite delay

        return self.limit(jobs, query)


# ─────────────────────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_naukri_job(item: dict, query: JobQuery) -> Job | None:
    # Title — Naukri uses CONTDESIG or 'post', NOT 'title'
    title = clean_text(
        item.get("CONTDESIG") or
        item.get("post") or
        item.get("role") or ""
    )
    if not title:
        return None

    company = clean_text(item.get("companyName") or item.get("CONTCOM") or "")

    # URL — urlStr is the canonical SEO URL
    url_path = item.get("urlStr") or item.get("nonStaticUrlFor") or ""
    job_url = f"{_BASE}{url_path}" if url_path.startswith("/") else url_path
    if not job_url:
        return None

    # Location — city is comma-separated list
    raw_city = clean_text(item.get("city") or item.get("CONTCITY") or "")
    city = normalize_city(raw_city.split(",")[0]) if raw_city else normalize_city(query.city)

    # Salary — minSal/maxSal in LPA (Lakhs Per Annum)
    min_sal = _to_float(item.get("minSal"))
    max_sal = _to_float(item.get("maxSal"))
    currency = item.get("currencySal", "INR") or "INR"
    salary = Money(
        min_amount = min_sal * 100_000 if min_sal else None,
        max_amount = max_sal * 100_000 if max_sal else None,
        currency   = currency,
        period     = SalaryPeriod.YEAR,
        raw_text   = item.get("SALARY", ""),
    )

    # Experience
    exp_min = _to_float(item.get("minExp"))
    exp_max = _to_float(item.get("maxExp"))

    # Skills
    raw_skills = item.get("keywords") or ""
    if isinstance(raw_skills, str):
        skills = normalize_skills(raw_skills.split(","))
    elif isinstance(raw_skills, list):
        skills = normalize_skills(raw_skills)
    else:
        skills = []

    # Date
    date_raw = item.get("addDate") or item.get("dateAdded") or ""
    date_posted = _parse_naukri_date(date_raw)

    # Work mode
    job_opts = " ".join(str(v) for v in [
        item.get("wfhType", ""),
        item.get("jobOptions", ""),
        item.get("jobtype", ""),
    ])
    work_mode = parse_work_mode(job_opts)

    # Employment type
    emp_type = clean_text(item.get("employmentType") or item.get("jobtype") or "")

    # Job kind
    if "intern" in title.lower() or item.get("internshipStartDate"):
        job_kind = JobKind.INTERNSHIP
    else:
        job_kind = JobKind.JOB

    # Description (truncated from API)
    desc = clean_text(item.get("jobDesc") or "")

    return Job(
        title          = title,
        company        = company,
        source         = "naukri",
        job_url        = job_url,
        location       = raw_city,
        city           = city,
        country        = "India",
        work_mode      = work_mode,
        job_kind       = job_kind,
        employment_type= emp_type,
        salary         = salary,
        experience_min = exp_min,
        experience_max = exp_max,
        experience_text= f"{exp_min}-{exp_max} yrs" if exp_min is not None else "",
        skills         = skills,
        date_posted    = date_posted,
        description    = desc,
        source_job_id  = str(item.get("jobId") or ""),
        raw            = {"source_card": "naukri_v2"},
    )


def _to_float(val) -> float | None:
    try:
        return float(val) if val not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        return None


def _parse_naukri_date(raw: str) -> str | None:
    """Parse Naukri date formats like '09-Jun-2024' or epoch ms."""
    if not raw:
        return None
    # Try numeric epoch
    try:
        ts = int(raw)
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
    except (ValueError, TypeError, OSError):
        pass
    # Try 'dd-Mon-yyyy'
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return parse_date(raw)
