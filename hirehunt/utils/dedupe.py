"""Duplicate detection for cross-source job results."""

from __future__ import annotations

from hashlib import sha256
import re

from hirehunt.models import Job
from hirehunt.utils.normalization import normalize_url


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def job_identity(job: Job) -> str:
    url = normalize_url(job.job_url or job.apply_url)
    if url:
        return f"url:{url}"
    if job.source_job_id:
        return f"id:{job.source}:{job.source_job_id}"
    parts = [_slug(job.title), _slug(job.company), _slug(job.city or job.location), _slug(job.country)]
    raw = "|".join(parts)
    return "hash:" + sha256(raw.encode("utf-8")).hexdigest()


def deduplicate_jobs(jobs: list[Job]) -> tuple[list[Job], int]:
    seen: set[str] = set()
    unique: list[Job] = []
    duplicates = 0
    for job in jobs:
        identity = job_identity(job)
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        unique.append(job)
    return unique, duplicates
