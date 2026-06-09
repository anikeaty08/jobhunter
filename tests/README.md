# `tests/` — Test Suite

Unit and integration tests for the jobhunter framework.

## Running Tests

```bash
# Install dev dependencies
pip install -e .
pip install pytest

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_normalization.py -v
```

## Test Files

| File | What it tests |
|---|---|
| `test_normalization.py` | `parse_money`, `normalize_city`, `clean_text`, `parse_date`, `parse_work_mode` |
| `test_parsers.py` | HTML parsers for Internshala, LinkedIn, Shine, Naukri — uses fixture HTML |
| `test_filter_matrix.py` | Soft filtering logic — salary, city, skills, date, experience |
| `test_dedupe_filter_rank.py` | Deduplication, ranking, `match_score` calculation |
| `test_v02_features.py` | End-to-end tests for v0.2 features — pagination, FAANG sources |

## Writing New Tests

Add a file `tests/test_my_feature.py`:

```python
import pytest
from jobhunter.models import Job, JobKind, WorkMode, Money
from jobhunter.query import JobQuery


def make_job(**kwargs) -> Job:
    defaults = dict(
        title="Python Developer",
        company="Acme Corp",
        source="test",
        job_url="https://example.com/job/1",
    )
    return Job(**{**defaults, **kwargs})


def test_my_feature():
    job = make_job(title="ML Engineer Intern")
    assert job.title == "ML Engineer Intern"
```

## Test Fixtures

Fixture HTML files (if needed) go in `tests/fixtures/`:

```
tests/
  fixtures/
    internshala_page.html
    shine_nextdata.json
    naukri_response.json
```

Load them in tests with:

```python
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
```
