"""JSON export."""

from __future__ import annotations

import json

from jobhunter.models import Job


def to_json(jobs: list[Job], path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump([job.to_dict() for job in jobs], handle, ensure_ascii=False, indent=2)
