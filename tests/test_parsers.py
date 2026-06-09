import unittest
import json

from jobhunter.query import JobQuery
from jobhunter.scrapers.indeed import parse_indeed_graphql_response
from jobhunter.scrapers.internshala import parse_internshala_jobs
from jobhunter.scrapers.linkedin import parse_linkedin_jobs
from jobhunter.scrapers.unstop import parse_unstop_jobs


class ParserTests(unittest.TestCase):
    def test_internshala_parser(self):
        html = """
        <div class="individual_internship" id="individual_internship_1" internshipid="1" data-href="/internship/detail/python-intern">
          <a class="job-title-href" href="/internship/detail/python-intern">Python Intern</a>
          <div class="company-name">Acme Labs</div>
          <span class="location_link">Bangalore</span>
          <span class="stipend">₹15,000 /month</span>
          <div class="round_tabs_container"><span>Python</span><span>Django</span></div>
        </div>
        """
        jobs = parse_internshala_jobs(html, JobQuery(role="python intern", search_term="python intern", city="Bangalore"))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].city, "Bengaluru")
        self.assertEqual(jobs[0].stipend.min_amount, 15000)

    def test_indeed_parser(self):
        payload = {
            "data": {
                "jobSearch": {
                    "pageInfo": {"nextCursor": "next"},
                    "results": [
                        {
                            "job": {
                                "key": "abc123",
                                "title": "Backend Engineer Intern",
                                "datePublished": 1780963200000,
                                "description": {"html": "<p>Python internship</p>"},
                                "location": {
                                    "countryCode": "IN",
                                    "admin1Code": "KA",
                                    "city": "Bangalore",
                                    "formatted": {"short": "Bangalore, KA", "long": "Bangalore, KA, IN"},
                                },
                                "compensation": {
                                    "baseSalary": {"unitOfWork": "MONTH", "range": {"min": 15000, "max": 25000}},
                                    "estimated": None,
                                    "currencyCode": "INR",
                                },
                                "attributes": [{"key": "VDTG7", "label": "Internship"}],
                                "employer": {"name": "Acme", "relativeCompanyPageUrl": "/cmp/acme", "dossier": {}},
                                "recruit": {"viewJobUrl": "https://example.com/apply"},
                            }
                        }
                    ],
                }
            }
        }
        jobs, cursor = parse_indeed_graphql_response(
            json.dumps(payload),
            JobQuery(role="backend engineer", search_term="backend engineer", city="Bengaluru", country="India"),
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(cursor, "next")
        self.assertEqual(jobs[0].source_job_id, "abc123")
        self.assertEqual(jobs[0].job_url, "https://in.indeed.com/viewjob?jk=abc123")
        self.assertEqual(jobs[0].city, "Bengaluru")
        self.assertEqual(jobs[0].salary.min_amount, 15000)

    def test_linkedin_parser(self):
        html = """
        <li class="base-card">
          <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/12345"></a>
          <h3 class="base-search-card__title">Software Engineer Intern</h3>
          <h4 class="base-search-card__subtitle">Acme</h4>
          <span class="job-search-card__location">Remote</span>
        </li>
        """
        jobs = parse_linkedin_jobs(html, JobQuery(role="software engineer intern", search_term="software engineer intern"))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source_job_id, "12345")

    def test_unstop_parser(self):
        html = """
        <div class="opportunity-card">
          <a href="/jobs/backend-intern-acme-123">Backend Intern | Acme</a>
          <span class="salary">₹25,000 per month</span>
        </div>
        """
        jobs = parse_unstop_jobs(html, JobQuery(role="backend intern", search_term="backend intern", city="Bengaluru"))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "Acme")

    def test_linkedin_parser_accepts_blocked_empty_page(self):
        jobs = parse_linkedin_jobs("<html><title>authwall</title></html>", JobQuery(role="software engineer"))
        self.assertEqual(jobs, [])


if __name__ == "__main__":
    unittest.main()
