# `scrapers/` — Job Source Scrapers

One file per source. Each scraper extends `BaseScraper` and implements a single `search(query) → list[Job]` method.

## Scraper Index

| File | Source | Region | Endpoint / Method |
|---|---|---|---|
| `naukri.py` | Naukri | 🇮🇳 India | `GET /jobapi/v2/search` — REST JSON |
| `shine.py` | Shine.com | 🇮🇳 India | `__NEXT_DATA__` SSR JSON in HTML |
| `internshala.py` | Internshala | 🇮🇳 India | HTML scraping + `?page=N` |
| `unstop.py` | Unstop | 🇮🇳 India | `GET /api/public/opportunity/search-result` — hackathons API |
| `linkedin.py` | LinkedIn | 🌍 Global | Guest HTML API — no auth |
| `indeed.py` | Indeed | 🌍 Global | `POST apis.indeed.com/graphql` — GraphQL |
| `faang.py` | Google, Amazon, Meta, Apple, Netflix, Microsoft | 🌍 Global | Amazon: REST API. Others: LinkedIn company-filtered |
| `base.py` | — | — | `BaseScraper` abstract class |

## BaseScraper Contract

```python
class BaseScraper(ABC):
    source: str = ""           # unique source name e.g. "naukri"
    default_country: str = ""  # e.g. "India"

    def search(self, query: JobQuery) -> list[Job]: ...   # implement this
    def fetch(self, url) -> FetchResponse | None: ...     # HTML GET
    def get_json(self, url, *, params, headers): ...      # JSON GET
    def post_json(self, url, *, headers, payload): ...    # JSON POST
    def limit(self, jobs, query) -> list[Job]: ...        # slice to results_wanted
```

## Adding a New Scraper

1. Create `scrapers/my_source.py`:

```python
from jobhunter.scrapers.base import BaseScraper
from jobhunter.models import Job
from jobhunter.query import JobQuery

class MySourceScraper(BaseScraper):
    source = "my_source"

    def search(self, query: JobQuery) -> list[Job]:
        resp = self.get_json("https://api.my-source.com/jobs", params={"q": query.normalized_term})
        if not resp or resp.status_code != 200:
            return []
        data = json.loads(resp.text)
        return self.limit([_parse(item, query) for item in data["jobs"]], query)
```

2. Register it in `scrapers/__init__.py`:

```python
from jobhunter.scrapers.my_source import MySourceScraper

BUILTIN_SCRAPERS = [
    ...,
    MySourceScraper,
]
```

That's it — it's now available as `source="my_source"`.

## Reverse Engineering Notes

### Naukri
- `v3` returns 406 — only `v2` works
- Needs session cookies from a page warm-up request first
- Field names are abbreviated: `CONTDESIG` = title, `companyName` = company, `urlStr` = URL
- Salary in LPA (multiply × 100,000 to get INR)

### Shine
- All job data is in `__NEXT_DATA__` → `props.pageProps.initialState.jsrp.searchresult.data.results`
- Keys are abbreviated: `jJT`=title, `jCName`=company, `jSal`=salary, `jLoc`=location, `jKwd`=skills, `jPDate`=date, `jSlug`=URL slug
- 17,927 total listings, 897 pages, `?page=N` pagination

### Internshala
- City filter only works via URL slug: `/internships/python-intern-in-bengaluru/`
- AJAX endpoint `/internships_ajax/` ignores `location_list[]` — use HTML only
- Skills are in `.job_skill` elements

### Unstop
- The `opportunity/search-result` API **always returns hackathons/competitions** regardless of type params — this is by design
- Pagination: `page=N&size=N`, up to 1000 pages (10,000+ total)
- Organisation is a nested dict: `item["organisation"]["name"]`

### FAANG
- **Amazon**: `amazon.jobs/en/search.json` is a public REST API. `team` field is a dict — extract `team["label"]`
- **Google/Meta/Netflix/Microsoft**: Use LinkedIn guest API with `f_C` (company ID) filter
- **Apple**: `f_C=162479` returns 0 on guest API — uses keyword fallback (`"Apple python developer"`)
