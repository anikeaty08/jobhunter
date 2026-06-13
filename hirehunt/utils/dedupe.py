"""Duplicate detection for cross-source job results."""

from __future__ import annotations

from difflib import SequenceMatcher
from hashlib import sha256
import re

from hirehunt.models import Job
from hirehunt.policies import DedupeOutcome
from hirehunt.utils.normalization import normalize_url


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def job_identity(job: Job, mode: str = "strict", scope: str = "title-company-location-country") -> str:
    url = normalize_url(job.job_url or job.apply_url)
    if mode == "strict" and url:
        return f"url:{url}"
    if job.source_job_id and mode == "strict":
        return f"id:{job.source}:{job.source_job_id}"
    parts = _identity_parts(job, scope)
    raw = "|".join(parts)
    return "hash:" + sha256(raw.encode("utf-8")).hexdigest()


def deduplicate_jobs_with_diagnostics(
    jobs: list[Job],
    mode: str = "strict",
    scope: str = "title-company-location-country",
) -> DedupeOutcome:
    if mode not in {"strict", "heuristic", "fuzzy", "none"}:
        raise ValueError("dedupe mode must be 'strict', 'heuristic', 'fuzzy', or 'none'")
    if mode == "none":
        return DedupeOutcome(list(jobs))

    seen: set[str] = set()
    unique: list[Job] = []
    duplicates = 0
    duplicates_by_source: dict[str, int] = {}
    fuzzy_keys: list[tuple[Job, tuple[str, ...]]] = []
    for job in jobs:
        if mode == "fuzzy":
            current = tuple(_identity_parts(job, scope))
            if _is_fuzzy_duplicate(current, fuzzy_keys):
                duplicates += 1
                duplicates_by_source[job.source] = duplicates_by_source.get(job.source, 0) + 1
                continue
            fuzzy_keys.append((job, current))
            unique.append(job)
            continue

        identity = job_identity(job, mode=mode, scope=scope)
        if identity in seen:
            duplicates += 1
            duplicates_by_source[job.source] = duplicates_by_source.get(job.source, 0) + 1
            continue
        seen.add(identity)
        unique.append(job)
    return DedupeOutcome(unique, duplicates, duplicates_by_source)


def deduplicate_jobs(
    jobs: list[Job],
    mode: str = "strict",
    scope: str = "title-company-location-country",
) -> tuple[list[Job], int]:
    outcome = deduplicate_jobs_with_diagnostics(jobs, mode=mode, scope=scope)
    return outcome.jobs, outcome.duplicates


def _identity_parts(job: Job, scope: str) -> list[str]:
    parts: list[str] = []
    for field_name in scope.split("-"):
        field_name = field_name.strip()
        if field_name == "title":
            parts.append(_slug(job.title))
        elif field_name == "company":
            parts.append(_slug(job.company))
        elif field_name == "location":
            parts.append(_slug(job.city or job.location))
        elif field_name == "country":
            parts.append(_slug(job.country))
    return parts


def _is_fuzzy_duplicate(current: tuple[str, ...], prior: list[tuple[Job, tuple[str, ...]]]) -> bool:
    title = current[0] if current else ""
    company = current[1] if len(current) > 1 else ""
    location = current[2] if len(current) > 2 else ""
    for _, existing in prior:
        existing_title = existing[0] if existing else ""
        existing_company = existing[1] if len(existing) > 1 else ""
        existing_location = existing[2] if len(existing) > 2 else ""
        if company and existing_company and company != existing_company:
            continue
        if location and existing_location and location != existing_location:
            continue
        if SequenceMatcher(None, title, existing_title).ratio() >= 0.88:
            return True
    return False
