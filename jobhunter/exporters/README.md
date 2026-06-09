# `exporters/` — Output Formatters

Converts `list[Job]` into different output formats.

## Modules

| File | Function | Output |
|---|---|---|
| `csv.py` | `to_csv(jobs, path)` | CSV file |
| `json.py` | `to_json(jobs, path)` | JSON file (array of objects) |
| `dataframe.py` | `to_dataframe(jobs)` | `pandas.DataFrame` |

## Usage

```python
from jobhunter import scrape_jobs
from jobhunter.exporters.csv import to_csv
from jobhunter.exporters.json import to_json
from jobhunter.exporters.dataframe import to_dataframe

jobs = scrape_jobs("python developer", sources=["naukri", "shine"])

# Save to CSV
to_csv(jobs, "jobs.csv")

# Save to JSON
to_json(jobs, "jobs.json")

# Get pandas DataFrame
df = to_dataframe(jobs)
print(df[["title", "company", "city", "salary"]].head(10))
```

## CSV Column Order

```
title, company, source, job_url, location, city, country,
work_mode, job_kind, employment_type, experience_min, experience_max,
salary_min, salary_max, salary_currency, salary_period,
skills, date_posted, deadline, match_score
```

## Adding a New Exporter

```python
# exporters/my_format.py
from jobhunter.models import Job

def to_my_format(jobs: list[Job], path: str) -> None:
    with open(path, "w") as f:
        for job in jobs:
            f.write(job.to_json() + "\n")
```
