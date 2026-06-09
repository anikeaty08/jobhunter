"""Pandas DataFrame export."""

from __future__ import annotations

from jobhunter.models import Job


def to_dataframe(jobs: list[Job]):
    import pandas as pd

    return pd.DataFrame([job.to_dict() for job in jobs])
