"""Post-scrape filtering — all filters are OPTIONAL/SOFT by default.

Rules:
- Filters only drop a job if the data is *present* AND *mismatches*.
- If the job is missing a field (city, salary, date etc.), it PASSES through.
- This prevents false negatives from incomplete scraped data.
- Only `exclude` (blacklist) and `posted_within_days` are strict.
"""

from __future__ import annotations

from datetime import date, timedelta

from hirehunt.models import Job, JobKind, WorkMode
from hirehunt.query import JobQuery


def _contains_any(value: str, needles: list[str]) -> bool:
    lowered = value.lower()
    return any(needle.lower() in lowered for needle in needles if needle)


def filter_jobs(jobs: list[Job], query: JobQuery) -> list[Job]:
    filtered: list[Job] = []
    excludes = [item.lower() for item in query.exclude]
    today = date.today()

    for job in jobs:
        searchable = " ".join([job.title, job.company, job.description, " ".join(job.skills)]).lower()

        # ── Exclude / blacklist (always strict) ────────────────────────────
        if excludes and any(excluded in searchable for excluded in excludes):
            continue

        # ── City filter (SOFT: skip if job.city is empty/unknown) ──────────
        # Normalize both sides so Bangalore==Bengaluru, Calcutta==Kolkata etc.
        if query.city and job.city:
            from hirehunt.utils.normalization import normalize_city
            query_canonical = normalize_city(query.city).lower()
            job_canonical = normalize_city(job.city).lower()
            if query_canonical not in job_canonical and job_canonical not in query_canonical:
                continue

        # ── Multi-city filter (SOFT) ────────────────────────────────────────
        if query.cities and job.city:
            from hirehunt.utils.normalization import normalize_city
            job_canonical = normalize_city(job.city).lower()
            if not any(normalize_city(c).lower() in job_canonical or job_canonical in normalize_city(c).lower()
                       for c in query.cities):
                continue

        # ── Country filter (SOFT) ───────────────────────────────────────────
        if query.country and job.country:
            if query.country.lower() not in job.country.lower():
                continue

        # ── Remote filter ───────────────────────────────────────────────────
        # SOFT: WorkMode.UNKNOWN passes (we don't know if it's remote or not)
        if query.remote is True and job.work_mode not in {WorkMode.REMOTE, WorkMode.HYBRID, WorkMode.UNKNOWN}:
            continue
        if query.remote is False and job.work_mode == WorkMode.REMOTE:
            continue

        # ── Fresher / experience filter (SOFT) ─────────────────────────────
        # Only drop if explicitly states experience > threshold
        if query.fresher is True and job.experience_min and job.experience_min > 1:
            continue
        if query.experience_max is not None and job.experience_min and job.experience_min > query.experience_max:
            continue

        # ── Skills filter (SOFT) ───────────────────────────────────────────
        # Pass if: no structured skills on job (data missing) OR any skill matches
        # Only drop if the job HAS skills listed and NONE match
        if query.skills:
            skill_terms = [skill.lower() for skill in query.skills]
            structured_skills = set(job.skills)
            has_skills_data = bool(structured_skills)
            skill_in_text = any(skill in searchable for skill in skill_terms)

            if has_skills_data and not structured_skills.intersection(skill_terms) and not skill_in_text:
                continue
            # If job has no skills data → let it through (trust the search engine)

        # ── Salary filter (SOFT: only drop if salary data present AND too low)
        if query.salary_min is not None:
            amount = job.salary.max_amount or job.salary.min_amount
            if amount is not None and amount < query.salary_min:
                continue

        # ── Stipend filter (SOFT: same logic) ──────────────────────────────
        if query.stipend_min is not None:
            amount = job.stipend.max_amount or job.stipend.min_amount
            if amount is not None and amount < query.stipend_min:
                continue

        # ── Posted-within filter (SOFT: jobs with no date pass through) ────
        if query.posted_within_days is not None and job.date_posted:
            try:
                posted = date.fromisoformat(job.date_posted)
                if posted < today - timedelta(days=query.posted_within_days):
                    continue
            except ValueError:
                pass  # malformed date → let through

        # ── Job kind filter ─────────────────────────────────────────────────
        if query.job_kind:
            wanted = {query.job_kind} if isinstance(query.job_kind, str) else set(query.job_kind)
            if str(job.job_kind) not in wanted and job.job_kind not in wanted:
                continue

        # ── Keyword relevance (SOFT: only drop if clearly irrelevant) ───────
        # Split into individual words; drop only if NONE of the meaningful words appear
        if query.normalized_term and not _contains_any(searchable, [query.normalized_term]):
            terms = [part for part in query.normalized_term.split() if len(part) > 2]
            if terms and not _contains_any(searchable, terms):
                continue

        # ── Infer job kind from query (cleanup) ────────────────────────────
        if job.job_kind == JobKind.UNKNOWN and "intern" in query.normalized_term.lower():
            job.job_kind = JobKind.INTERNSHIP

        filtered.append(job)
    return filtered
