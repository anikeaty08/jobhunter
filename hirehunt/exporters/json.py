"""JSON export."""

from __future__ import annotations

import json

from hirehunt.exporters.csv import _job_to_flat_dict
from hirehunt.models import Job


def to_json(jobs: list[Job], path: str, *, full: bool = False) -> None:
    payload = [job.to_dict() if full else _job_to_flat_dict(job) for job in jobs]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
