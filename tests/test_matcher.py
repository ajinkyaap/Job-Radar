from datetime import UTC, datetime
import unittest

from matcher import calculate
from models import Job


PROFILE = {
    "experience_years": 4.5,
    "max_job_age_days": 21,
    "minimum_skill_groups": 3,
    "preferred_locations": ["remote", "india", "pune"],
    "acceptable_locations": ["remote", "india", "worldwide", "global", "pune"],
    "target_title_terms": ["software engineer", "backend engineer", "java engineer"],
    "excluded_title_terms": ["intern", "manager", "principal", "staff engineer"],
    "priority_companies": ["Stripe"],
}


def job(title="Senior Backend Engineer", location="Pune, India", description=""):
    return Job(
        company="Stripe",
        title=title,
        location=location,
        description=description,
        apply_url="https://example.test/job",
        posted_at=datetime.now(UTC),
        days_old=1,
        remote=False,
        source="Test",
    )


class MatcherTests(unittest.TestCase):
    def test_resume_aligned_job_is_high_priority(self):
        result = calculate(job(description=(
            "Java Spring Boot microservices Kafka REST API PostgreSQL AWS Docker "
            "Kubernetes Jenkins banking Grafana. Requires 4+ years."
        )), PROFILE)
        self.assertGreaterEqual(result.score, 90)
        self.assertEqual(result.priority, "HIGH")
        self.assertIn("kafka", result.matched_skills)

    def test_non_target_title_is_rejected(self):
        result = calculate(job(title="Engineering Manager", description="Java Spring Boot"), PROFILE)
        self.assertEqual(result.score, 0)

    def test_out_of_scope_location_is_rejected(self):
        result = calculate(job(location="New York, United States", description="Java Spring Boot Kafka"), PROFILE)
        self.assertEqual(result.score, 0)


if __name__ == "__main__":
    unittest.main()
