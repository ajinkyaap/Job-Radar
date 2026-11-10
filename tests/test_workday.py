import unittest
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from ats.workday import fetch_workday_jobs


class WorkdayConnectorTests(unittest.TestCase):
    @patch("ats.workday.requests.post")
    def test_parses_public_cxs_response(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "jobPostings": [{
                "title": "Senior Software Engineer - Payments",
                "locationsText": "Bengaluru, India",
                "externalPath": "/job/Bengaluru/Senior-Software-Engineer_JR-1",
                "bulletFields": ["Java", "Spring Boot", "Kafka"],
            }]
        }
        post.return_value = response
        jobs = fetch_workday_jobs([{
            "company": "Example Fintech",
            "host": "example.wd5.myworkdayjobs.com",
            "tenant": "example",
            "site": "ExternalCareers",
        }])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source, "Workday")
        self.assertIn("example.wd5.myworkdayjobs.com", jobs[0].apply_url)
        post.assert_called_once()

    @patch("ats.workday.requests.post")
    def test_failed_board_is_isolated(self, post):
        post.side_effect = RuntimeError("timeout")
        self.assertEqual(fetch_workday_jobs([{
            "company": "Broken", "host": "broken.wd1.myworkdayjobs.com",
            "tenant": "broken", "site": "Careers",
        }]), [])


if __name__ == "__main__":
    unittest.main()
