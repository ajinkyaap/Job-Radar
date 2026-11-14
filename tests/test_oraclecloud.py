import unittest
from unittest.mock import patch

from ats.oraclecloud import fetch_oracle_jobs


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"items": [{"requisitionList": [{
            "Id": "123", "Title": "Backend Software Engineer",
            "PrimaryLocation": "Mumbai, India", "PostedDate": "2026-11-10",
            "ShortDescriptionStr": "Java and Spring backend services",
        }]}]}


class OracleCloudTests(unittest.TestCase):
    @patch("ats.oraclecloud.requests.get", return_value=_Response())
    def test_normalizes_requisitions(self, get):
        jobs = fetch_oracle_jobs([{"company": "JPMC", "host": "jpmc.fa.oraclecloud.com", "site": "CX_1001"}])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source, "Oracle Cloud")
        self.assertIn("/job/123", jobs[0].apply_url)


if __name__ == "__main__":
    unittest.main()
