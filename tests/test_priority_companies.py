import unittest

from priority_companies import PRIORITY_COMPANIES, build_priority_queries


class PriorityCompanyTests(unittest.TestCase):
    def test_priority_registry_and_queries(self):
        self.assertGreaterEqual(len(PRIORITY_COMPANIES), 20)
        queries = build_priority_queries()
        self.assertGreaterEqual(len(queries), 20)
        self.assertTrue(all("software engineer" in query for query in queries))
        self.assertTrue(any("jpmorganchase.com" in query for query in queries))


if __name__ == "__main__":
    unittest.main()
