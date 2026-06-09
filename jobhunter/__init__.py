"""Backward-compat shim — 'import jobhunter' still works after rename to hirehunt."""
from hirehunt import *  # noqa: F401, F403
from hirehunt import scrape_jobs, Job, JobQuery  # noqa: F401
