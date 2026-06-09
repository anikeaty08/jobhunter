"""
models.py — Core data models for JobHunter
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
import json


@dataclass
class Job:
    # ── Required ──────────────────────────────────────────────
    title: str
    company: str
    source: str                        # internshala / linkedin / indeed / etc.
    job_url: str

    # ── Location ──────────────────────────────────────────────
    location: str = "N/A"
    city: str = "N/A"
    state: str = "N/A"
    country: str = "N/A"
    is_remote: bool = False

    # ── Job Details ───────────────────────────────────────────
    description: str = ""
    job_type: str = "N/A"             # fulltime / parttime / internship / contract
    experience_min: int = 0           # years
    experience_max: int = 0
    experience_text: str = "N/A"

    # ── Compensation ──────────────────────────────────────────
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "INR"
    salary_text: str = "Not disclosed"
    stipend: str = "N/A"             # For internships

    # ── Skills ────────────────────────────────────────────────
    skills: list = field(default_factory=list)

    # ── Dates ─────────────────────────────────────────────────
    date_posted: Optional[str] = None
    date_posted_text: str = "N/A"
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # ── Company Details ───────────────────────────────────────
    company_url: str = "N/A"
    company_rating: str = "N/A"
    company_industry: str = "N/A"

    # ── Extra ─────────────────────────────────────────────────
    job_id: str = ""
    duration: str = "N/A"            # For internships
    apply_url: str = ""
    easy_apply: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __str__(self) -> str:
        return f"{self.title} @ {self.company} | {self.location} | {self.source}"