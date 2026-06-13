"""CSV export."""

from __future__ import annotations

import csv

from hirehunt.models import Job


def to_csv(jobs: list[Job], path: str, *, full: bool = False) -> None:
    rows = [job.to_dict() if full else _job_to_flat_dict(job) for job in jobs]
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            handle.write("")
        return
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _job_to_flat_dict(job: Job) -> dict[str, object]:
    return {
        "title": job.title,
        "company": job.company,
        "source": job.source,
        "job_url": job.job_url,
        "apply_url": job.apply_url,
        "location": job.location,
        "city": job.city,
        "state": job.state,
        "country": job.country,
        "work_mode": str(job.work_mode),
        "job_kind": str(job.job_kind),
        "employment_type": job.employment_type,
        "experience_min": job.experience_min,
        "experience_max": job.experience_max,
        "experience_text": job.experience_text,
        "salary_min": job.salary.min_amount,
        "salary_max": job.salary.max_amount,
        "salary_currency": job.salary.currency,
        "salary_period": str(job.salary.period),
        "salary_raw": job.salary.raw_text,
        "stipend_min": job.stipend.min_amount,
        "stipend_max": job.stipend.max_amount,
        "stipend_currency": job.stipend.currency,
        "stipend_period": str(job.stipend.period),
        "stipend_raw": job.stipend.raw_text,
        "skills": "|".join(job.skills),
        "description": job.description,
        "date_posted": job.date_posted,
        "deadline": job.deadline,
        "company_rating": job.company_rating,
        "company_industry": job.company_industry,
        "source_job_id": job.source_job_id,
        "easy_apply": job.easy_apply,
        "match_score": job.match_score,
        "reasons": "|".join(job.reasons),
        "warnings": "|".join(job.warnings),
    }
