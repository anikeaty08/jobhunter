"""Result scoring and explainability."""

from __future__ import annotations

from datetime import date
import re

from hirehunt.models import Job, WorkMode
from hirehunt.query import JobProfile, JobQuery


def rank_jobs(jobs: list[Job], query: JobQuery) -> list[Job]:
    query_text = query.normalized_term.lower().strip()
    query_terms = [term.lower() for term in query.normalized_term.split() if len(term) > 2]
    skills = [skill.lower() for skill in query.skills]
    today = date.today()

    for job in jobs:
        score = 0.0
        reasons: list[str] = []
        warnings: list[str] = []
        title = job.title.lower()
        description = job.description.lower()

        strength = _title_match_strength(title, query_text, query_terms)
        if strength == "exact":
            score += 25
            reasons.append("exact title match")
        elif strength == "prefix":
            score += 15
            reasons.append("title starts with query")
        elif strength == "strong":
            score += 10
            reasons.append("title matches search intent")
        elif strength == "weak":
            score += 2
            reasons.append("query appears in title")

        skill_hits = sorted(set(skills).intersection(skill.lower() for skill in job.skills))
        text_skill_hits = [skill for skill in skills if skill in title or skill in description]
        combined_skill_hits = sorted(set(skill_hits + text_skill_hits))
        if combined_skill_hits:
            score += min(16, 5 * len(combined_skill_hits))
            reasons.append("skills match: " + ", ".join(combined_skill_hits[:5]))
        elif skills:
            warnings.append("no requested skills found")

        if query.company_terms and any(term.lower() in job.company.lower() for term in query.company_terms):
            score += 8
            reasons.append("company matches")

        city_matched = False
        if query.city and job.city and query.city.lower() in job.city.lower():
            score += 8
            city_matched = True
            reasons.append("city matches")
        if query.cities and job.city and any(city.lower() in job.city.lower() for city in query.cities):
            score += 8
            city_matched = True
            reasons.append("preferred city matches")
        if query.city and job.city and not city_matched:
            score -= 15
            warnings.append("city mismatch")

        if query.remote is True and job.work_mode == WorkMode.REMOTE:
            score += 5
            reasons.append("remote role")
        if query.work_mode and str(job.work_mode) == str(query.work_mode).lower():
            score += 5
            reasons.append("work mode matches")

        if query.fresher and (job.experience_min is None or job.experience_min <= 1):
            score += 6
            reasons.append("fresher friendly")
        if query.salary_min and (job.salary.max_amount or 0) >= query.salary_min:
            score += 5
            reasons.append("salary target met")
        if query.stipend_min and (job.stipend.max_amount or 0) >= query.stipend_min:
            score += 5
            reasons.append("stipend target met")
        if job.salary.has_value or job.stipend.has_value:
            score += 5
            reasons.append("has compensation data")
        if job.date_posted:
            score += 5
            reasons.append("has posting date")
            recency_bonus, recency_reason = _posting_recency_bonus(job.date_posted, today)
            score += recency_bonus
            if recency_reason:
                reasons.append(recency_reason)

        profile_score, profile_reasons, profile_warnings = score_for_profile(job, query.profile)
        score += profile_score
        reasons.extend(profile_reasons)
        warnings.extend(profile_warnings)

        if not job.description:
            warnings.append("description unavailable")
        if query_terms and strength == "none" and any(term in description for term in query_terms):
            score -= 10
            warnings.append("query only appears in description")
        if "senior" in title and query.fresher:
            score -= 15
            warnings.append("senior title may not fit fresher profile")

        job.match_score = max(0.0, min(100.0, score))
        job.reasons = _dedupe_strings(reasons)
        job.warnings = _dedupe_strings(warnings)

    return sorted(
        jobs,
        key=lambda item: (item.match_score, _safe_posted_sort(item.date_posted), item.title.lower()),
        reverse=True,
    )


def score_for_profile(job: Job, profile: JobProfile | None) -> tuple[float, list[str], list[str]]:
    if profile is None:
        return 0.0, [], []

    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []
    title = job.title.lower()
    company = job.company.lower()

    title_hits = [wanted for wanted in profile.preferred_titles if wanted.lower() in title]
    if title_hits:
        score += min(18, 6 * len(title_hits))
        reasons.append("profile title preference matched")

    skill_hits = sorted(set(skill.lower() for skill in profile.skills).intersection(skill.lower() for skill in job.skills))
    if skill_hits:
        score += min(24, 6 * len(skill_hits))
        reasons.append("profile skills matched: " + ", ".join(skill_hits[:5]))

    if profile.preferred_companies and any(name.lower() in company for name in profile.preferred_companies):
        score += 10
        reasons.append("preferred company matched")

    if profile.excluded_companies and any(name.lower() in company for name in profile.excluded_companies):
        score -= 40
        warnings.append("excluded company matched")

    if profile.preferred_cities and job.city:
        if any(city.lower() in job.city.lower() for city in profile.preferred_cities):
            score += 8
            reasons.append("profile city preference matched")

    if profile.remote_preferred and job.work_mode == WorkMode.REMOTE:
        score += 8
        reasons.append("profile remote preference matched")

    if profile.fresher and (job.experience_min is None or job.experience_min <= 1):
        score += 8
        reasons.append("profile fresher fit")

    if profile.experience_years is not None:
        if job.experience_min is not None and job.experience_min > profile.experience_years:
            score -= 12
            warnings.append("experience requirement may be high")
        elif job.experience_max is None or job.experience_max >= profile.experience_years:
            score += 6
            reasons.append("experience range fits profile")

    if profile.min_salary is not None and (job.salary.max_amount or 0) >= profile.min_salary:
        score += 6
        reasons.append("profile salary target met")

    if profile.min_stipend is not None and (job.stipend.max_amount or 0) >= profile.min_stipend:
        score += 6
        reasons.append("profile stipend target met")

    return score, reasons, warnings


def _title_match_strength(title: str, query_text: str, query_terms: list[str]) -> str:
    if not query_text:
        return "none"
    normalized_title = _normalize_match_text(title)
    normalized_query = _normalize_match_text(query_text)
    if normalized_title == normalized_query:
        return "exact"
    if normalized_title.startswith(normalized_query):
        return "prefix"
    if query_terms and all(term in normalized_title for term in query_terms):
        return "strong"
    if normalized_query and normalized_query in normalized_title:
        return "weak"
    return "none"


def _normalize_match_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _posting_recency_bonus(value: str | None, today: date) -> tuple[float, str]:
    if not value:
        return 0.0, ""
    try:
        posted = date.fromisoformat(value)
    except ValueError:
        return 0.0, ""
    age = (today - posted).days
    if age <= 0:
        return 3.0, "posted today"
    if age == 1:
        return 2.0, "posted yesterday"
    if age <= 7:
        return 1.0, "recent posting"
    return 0.0, ""


def _safe_posted_sort(value: str | None) -> str:
    return value or ""


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
