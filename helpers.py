"""
utils/helpers.py — Text cleaning, date parsing, deduplication
"""

import re
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional
from dateutil import parser as dateparser

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Strip HTML, extra whitespace from text."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_date(date_str: str) -> Optional[str]:
    """Parse various date formats into ISO format."""
    if not date_str or date_str in ("N/A", ""):
        return None
    try:
        # Handle relative dates
        date_str_lower = date_str.lower().strip()
        now = datetime.now()

        if "just now" in date_str_lower or "today" in date_str_lower:
            return now.strftime("%Y-%m-%d")
        if "yesterday" in date_str_lower:
            return (now - timedelta(days=1)).strftime("%Y-%m-%d")

        match = re.search(r'(\d+)\s*(hour|day|week|month|year)', date_str_lower)
        if match:
            n, unit = int(match.group(1)), match.group(2)
            delta = {
                "hour": timedelta(hours=n),
                "day": timedelta(days=n),
                "week": timedelta(weeks=n),
                "month": timedelta(days=n * 30),
                "year": timedelta(days=n * 365),
            }.get(unit, timedelta(0))
            return (now - delta).strftime("%Y-%m-%d")

        # Try direct parsing
        dt = dateparser.parse(date_str, fuzzy=True)
        return dt.strftime("%Y-%m-%d") if dt else None
    except Exception:
        return None


def parse_experience(text: str) -> tuple[int, int]:
    """Extract min/max experience from text like '2-5 years' or 'Fresher'."""
    if not text:
        return 0, 0
    text_lower = text.lower()
    if any(w in text_lower for w in ["fresher", "0 year", "no experience", "entry"]):
        return 0, 1

    match = re.search(r'(\d+)\s*[-–to]+\s*(\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))

    match = re.search(r'(\d+)\+?\s*year', text)
    if match:
        n = int(match.group(1))
        return n, n + 5

    return 0, 0


def extract_salary(text: str) -> tuple[Optional[float], Optional[float], str]:
    """Extract min/max salary and currency from text."""
    if not text:
        return None, None, "INR"

    currency = "INR"
    if "$" in text or "USD" in text.upper():
        currency = "USD"
    elif "£" in text or "GBP" in text.upper():
        currency = "GBP"

    # Remove non-numeric except . , -
    text_clean = re.sub(r'[^\d.,\-–LKkMm]', ' ', text)

    # Handle LPA (Lakhs per annum) — common in India
    lpa_match = re.search(r'([\d.]+)\s*[-–]\s*([\d.]+)\s*[Ll][Pp][Aa]', text)
    if lpa_match:
        return float(lpa_match.group(1)) * 100000, float(lpa_match.group(2)) * 100000, "INR"

    # Handle K notation
    k_match = re.search(r'([\d.]+)[Kk]\s*[-–]\s*([\d.]+)[Kk]', text)
    if k_match:
        return float(k_match.group(1)) * 1000, float(k_match.group(2)) * 1000, currency

    # Handle plain range
    range_match = re.search(r'([\d,]+)\s*[-–]\s*([\d,]+)', text)
    if range_match:
        try:
            lo = float(range_match.group(1).replace(",", ""))
            hi = float(range_match.group(2).replace(",", ""))
            return lo, hi, currency
        except Exception:
            pass

    return None, None, currency


def deduplicate(jobs: list, key: str = "job_url") -> list:
    """Remove duplicate jobs by URL or composite key."""
    seen = set()
    unique = []
    for job in jobs:
        val = getattr(job, key, None) or job.get(key, "") if hasattr(job, key) else ""
        if not val:
            # Fallback: hash title+company
            val = hashlib.md5(f"{getattr(job, 'title', '')}_{getattr(job, 'company', '')}".encode()).hexdigest()
        if val not in seen:
            seen.add(val)
            unique.append(job)
    return unique


def job_hash(title: str, company: str) -> str:
    """Create a unique hash for a job."""
    return hashlib.md5(f"{title.lower().strip()}_{company.lower().strip()}".encode()).hexdigest()