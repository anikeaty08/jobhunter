"""Result scoring and explainability."""

from __future__ import annotations

from jobhunter.models import Job, WorkMode
from jobhunter.query import JobQuery


def rank_jobs(jobs: list[Job], query: JobQuery) -> list[Job]:
    terms = [term.lower() for term in query.normalized_term.split() if len(term) > 2]
    skills = [skill.lower() for skill in query.skills]

    for job in jobs:
        score = 0.0
        reasons: list[str] = []
        warnings: list[str] = []
        title = job.title.lower()
        description = job.description.lower()

        title_hits = [term for term in terms if term in title]
        if title_hits:
            score += min(35, 12 * len(title_hits))
            reasons.append("title matches search intent")

        skill_hits = sorted(set(skills).intersection(job.skills))
        if skill_hits:
            score += min(30, 8 * len(skill_hits))
            reasons.append("skills match: " + ", ".join(skill_hits[:5]))
        elif skills:
            warnings.append("no requested skills found")

        if query.remote is True and job.work_mode == WorkMode.REMOTE:
            score += 10
            reasons.append("remote role")
        if query.city and job.city and query.city.lower() in job.city.lower():
            score += 8
            reasons.append("city matches")
        if query.cities and job.city and any(city.lower() in job.city.lower() for city in query.cities):
            score += 8
            reasons.append("preferred city matches")
        if query.fresher and (job.experience_min is None or job.experience_min <= 1):
            score += 10
            reasons.append("fresher friendly")
        if query.salary_min and (job.salary.max_amount or 0) >= query.salary_min:
            score += 8
            reasons.append("salary target met")
        if query.stipend_min and (job.stipend.max_amount or 0) >= query.stipend_min:
            score += 8
            reasons.append("stipend target met")
        if job.date_posted:
            score += 5
            reasons.append("has posting date")
        if not job.description:
            warnings.append("description unavailable")
        if "senior" in title and query.fresher:
            warnings.append("senior title may not fit fresher profile")
            score -= 15
        if terms and not title_hits and not any(term in description for term in terms):
            score -= 10

        job.match_score = max(0.0, min(100.0, score))
        job.reasons = reasons
        job.warnings = warnings

    return sorted(jobs, key=lambda item: (item.match_score, item.date_posted or ""), reverse=True)
