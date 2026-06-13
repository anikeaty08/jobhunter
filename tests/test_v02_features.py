import asyncio
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import patch

import hirehunt
from hirehunt.cli import EXIT_NO_JOBS, main
from hirehunt.exporters.csv import _job_to_flat_dict
from hirehunt.engine import SearchEngine
from hirehunt.models import Job, Money, WorkMode
from hirehunt.query import JobProfile, JobQuery
from hirehunt.ranking import rank_jobs
from hirehunt.registry import ScraperRegistry
from hirehunt.registry import default_registry
from hirehunt.scrapers.base import BaseScraper
from hirehunt.utils.cache import PageCache


class MockScraper(BaseScraper):
    source = "mock"

    def search(self, query):
        return [
            Job(
                "Python Backend Intern",
                "Acme",
                "mock",
                "https://example.com/1",
                city=query.city,
                country=query.country,
                skills=["python", "fastapi"],
                work_mode=WorkMode.REMOTE,
                experience_min=0,
            )
        ]


def _fake_stats(**overrides):
    values = {
        "kept": 1,
        "parsed": 1,
        "duplicates": 0,
        "filtered_out": 0,
        "requests": 1,
        "completion": "partial",
        "completion_reason": "",
        "filter_reasons": {},
    }
    values.update(overrides)
    return type("Stats", (), values)()


class V02FeatureTests(unittest.TestCase):
    def test_public_version_is_exposed(self):
        self.assertTrue(hirehunt.__version__)

    def test_cli_validate_strict_exits_on_health_failure(self):
        buffer = io.StringIO()
        with patch("hirehunt.cli.validate_sources") as validate_sources:
            validate_sources.return_value = []
            with redirect_stdout(buffer):
                code = main(["validate", "python developer", "--strict"])
        self.assertEqual(code, 1)
        self.assertIn("Health issues:", buffer.getvalue())

    def test_cli_search_default_output_is_job_seeker_friendly(self):
        buffer = io.StringIO()
        fake_result = type(
            "Result",
            (),
            {
                "jobs": [
                    Job(
                        "Python Developer",
                        "UST",
                        "naukri",
                        "https://example.com/job",
                        city="Bengaluru",
                        experience_text="3-8 yrs",
                        date_posted=str(date.today()),
                        salary=Money(min_amount=400000, max_amount=600000, currency="INR"),
                        company_industry="IT Services",
                    )
                ],
                "stats": {"naukri": _fake_stats()},
                "errors": {},
                "warnings": [],
                "partial": False,
                "selected_sources": ["naukri"],
                "schema_version": "1.0",
            },
        )()
        with patch("hirehunt.cli.search_jobs", return_value=fake_result):
            with redirect_stdout(buffer):
                code = main(["search", "python developer", "--source", "naukri", "--city", "Bengaluru"])
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("Found 1 jobs", output)
        self.assertIn("1. Python Developer @ UST", output)
        self.assertIn("3-8 yrs", output)
        self.assertIn("INR 4-6 LPA", output)
        self.assertIn("IT Services", output)
        self.assertTrue("Source:" in output or "🔎" in output)

    def test_cli_json_stdout_has_stable_result_envelope(self):
        buffer = io.StringIO()
        fake_result = type(
            "Result",
            (),
            {
                "jobs": [Job("Python Developer", "UST", "naukri", "https://example.com/job", city="Bengaluru")],
                "stats": {"naukri": _fake_stats()},
                "errors": {},
                "warnings": [],
                "partial": False,
                "selected_sources": ["naukri"],
                "schema_version": "1.0",
            },
        )()
        with patch("hirehunt.cli.search_jobs", return_value=fake_result):
            with redirect_stdout(buffer):
                code = main(["search", "python developer", "--source", "naukri", "--output", "json"])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["command"], "search")
        self.assertIn("query", payload)
        self.assertIn("summary", payload)
        self.assertIn("jobs", payload)

    def test_cli_json_stdout_reports_no_jobs_exit_code(self):
        buffer = io.StringIO()
        fake_result = type(
            "Result",
            (),
            {
                "jobs": [],
                "stats": {},
                "errors": {},
                "warnings": ["No jobs found."],
                "partial": False,
                "selected_sources": ["naukri"],
                "schema_version": "1.0",
            },
        )()
        with patch("hirehunt.cli.search_jobs", return_value=fake_result):
            with redirect_stdout(buffer):
                code = main(["search", "python developer", "--source", "naukri", "--json-stdout"])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, EXIT_NO_JOBS)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "no_jobs")
        self.assertEqual(payload["exit_code"], EXIT_NO_JOBS)

    def test_saved_search_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/saved.json"
            add_buffer = io.StringIO()
            with redirect_stdout(add_buffer):
                add_code = main(
                    [
                        "saved-search",
                        "--file",
                        path,
                        "add",
                        "python-blr",
                        "python developer",
                        "--city",
                        "Bengaluru",
                        "--related",
                        "--fuzzy-dedupe",
                    ]
                )
            self.assertEqual(add_code, 0)

            show_buffer = io.StringIO()
            with redirect_stdout(show_buffer):
                show_code = main(["saved-search", "--file", path, "show", "python-blr"])
            self.assertEqual(show_code, 0)
            payload = json.loads(show_buffer.getvalue())
            self.assertEqual(payload["match_mode"], "broad")
            self.assertEqual(payload["dedupe_mode"], "fuzzy")

            list_buffer = io.StringIO()
            with redirect_stdout(list_buffer):
                list_code = main(["saved-search", "--file", path, "list", "--json"])
            self.assertEqual(list_code, 0)
            listed = json.loads(list_buffer.getvalue())
            self.assertIn("python-blr", listed)

    def test_flat_csv_export_flattens_salary_and_skills(self):
        row = _job_to_flat_dict(
            Job(
                "Python Developer",
                "UST",
                "naukri",
                "https://example.com/job",
                skills=["python", "django"],
            )
        )
        self.assertIn("salary_min", row)
        self.assertEqual(row["skills"], "python|django")

    def test_auto_sources_only_include_unstop_for_opportunity_searches(self):
        registry = default_registry()
        job_sources = registry.auto_sources("India", search_term="software developer")
        opportunity_sources = registry.auto_sources("India", search_term="coding hackathon")

        self.assertNotIn("unstop", job_sources)
        self.assertIn("unstop", opportunity_sources)

    def test_page_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = PageCache(tmp)
            cache.set("mock", "https://example.com/jobs", "<html>ok</html>")
            self.assertEqual(cache.get("mock", "https://example.com/jobs"), "<html>ok</html>")

    def test_zero_or_none_result_limit_is_uncapped(self):
        scraper = MockScraper()
        jobs = [
            Job("One", "Acme", "mock", "https://example.com/1"),
            Job("Two", "Acme", "mock", "https://example.com/2"),
        ]

        self.assertTrue(scraper.wants_more(jobs, JobQuery(results_wanted=0)))
        self.assertTrue(scraper.wants_more(jobs, JobQuery(results_wanted=None)))
        self.assertEqual(scraper.limit(jobs, JobQuery(results_wanted=0)), jobs)
        self.assertEqual(scraper.limit(jobs, JobQuery(results_wanted=None)), jobs)

    def test_async_search_path(self):
        registry = ScraperRegistry()
        registry.register(MockScraper)
        result = asyncio.run(
            SearchEngine(registry=registry).search_async(
                JobQuery(role="python intern", city="Bengaluru", country="India", sources=["mock"])
            )
        )
        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.jobs[0].city, "Bengaluru")

    def test_profile_ranking_adds_reasons(self):
        query = JobQuery(
            role="backend intern",
            city="Bengaluru",
            profile=JobProfile(
                skills=["python", "fastapi"],
                preferred_titles=["backend"],
                preferred_cities=["Bengaluru"],
                remote_preferred=True,
                fresher=True,
            ),
        )
        jobs = [
            Job(
                "Python Backend Intern",
                "Acme",
                "mock",
                "https://example.com/1",
                city="Bengaluru",
                skills=["python", "fastapi"],
                work_mode=WorkMode.REMOTE,
                experience_min=0,
            )
        ]
        ranked = rank_jobs(jobs, query)
        self.assertGreater(ranked[0].match_score, 50)
        self.assertTrue(any("profile" in reason for reason in ranked[0].reasons))


if __name__ == "__main__":
    unittest.main()
