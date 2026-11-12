import os
import unittest
from unittest.mock import Mock, patch
from ats.jooble import fetch_jooble_jobs

class JoobleTests(unittest.TestCase):
    @patch.dict(os.environ, {"JOOBLE_API_KEY": "test-key"})
    @patch("ats.jooble.requests.post")
    def test_parses_jobs(self, post):
        response = Mock(); response.raise_for_status.return_value = None
        response.json.return_value = {"jobs": [{"title": "Java Backend Engineer", "company": "Example", "location": "Pune, India", "snippet": "Java Spring Boot Kafka", "link": "https://example.test/job"}]}
        post.return_value = response
        jobs = fetch_jooble_jobs([{"keywords": "Java", "location": "India"}])
        self.assertEqual(len(jobs), 1); self.assertEqual(jobs[0].source, "Jooble")

if __name__ == "__main__": unittest.main()
