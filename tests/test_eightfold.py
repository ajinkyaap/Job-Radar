import unittest
from unittest.mock import patch

from ats.eightfold import fetch_eightfold_jobs


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"data": {"positions": [{
            "name": "Senior Backend Engineer",
            "locations": ["Bengaluru, India"],
            "postedTs": 1_700_000_000,
            "positionUrl": "/job/123",
            "workLocationOption": "hybrid",
        }]}}


class EightfoldTests(unittest.TestCase):
    @patch("ats.eightfold.requests.get", return_value=_Response())
    def test_normalizes_positions(self, get):
        jobs = fetch_eightfold_jobs([{
            "company": "Example",
            "host": "example.eightfold.ai",
            "domain": "example.com",
        }])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source, "Eightfold")
        self.assertEqual(jobs[0].location, "Bengaluru, India")
        self.assertTrue(jobs[0].apply_url.endswith("/job/123"))
        get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
