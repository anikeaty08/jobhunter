"""CSV export."""

from __future__ import annotations

import csv

from hirehunt.models import Job


def to_csv(jobs: list[Job], path: str) -> None:
    rows = [job.to_dict() for job in jobs]
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            handle.write("")
        return
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
