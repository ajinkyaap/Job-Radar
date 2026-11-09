import unittest
from bs4 import BeautifulSoup

from apply_assistant import eligibility_for_location, expired_reason
from gmail_reader import extract_verification_code


PROFILE = {
    "eligibility": {
        "india": {"work_authorization": "Yes", "requires_sponsorship": "No"},
        "other_countries": {"work_authorization": "No", "requires_sponsorship": "Yes"},
    }
}


class EligibilityTests(unittest.TestCase):
    def test_india_uses_authorized_policy(self):
        self.assertEqual(
            eligibility_for_location("Bengaluru, India", PROFILE)["work_authorization"], "Yes"
        )

    def test_foreign_and_unknown_locations_require_sponsorship(self):
        self.assertEqual(
            eligibility_for_location("Remote - United States", PROFILE)["requires_sponsorship"], "Yes"
        )
        self.assertEqual(
            eligibility_for_location("Remote", PROFILE)["work_authorization"], "No"
        )

    def test_closed_job_page_is_detected(self):
        class Body:
            def inner_text(self):
                return "This job is no longer available."

        class Page:
            def locator(self, _):
                return Body()

        class Response:
            status = 200

        self.assertIn("no longer available", expired_reason(Page(), Response()))

    def test_expired_banner_is_detected(self):
        class Body:
            def inner_text(self):
                return "This job is expired"

        class Page:
            def locator(self, _):
                return Body()

        class Response:
            status = 200

        self.assertIn("job is expired", expired_reason(Page(), Response()))

    def test_generic_expired_banner_is_detected(self):
        class Body:
            def inner_text(self):
                return "Status: Expired"

        class Page:
            def locator(self, _):
                return Body()

        class Response:
            status = 200

        self.assertIn("expired-posting", expired_reason(Page(), Response()))

    def test_greenhouse_code_with_separators_is_normalizable(self):
        text = "Copy and paste this code into the security code field on your application: # 5*79*820"
        self.assertEqual(extract_verification_code(text), "579820")

    def test_greenhouse_html_code_is_normalizable(self):
        text = "<div>Copy and paste this code into the security code field on your application:</div><div># 1*23*456</div>"
        self.assertEqual(extract_verification_code(BeautifulSoup(text, "html.parser").get_text(" ", strip=True)), "123456")
