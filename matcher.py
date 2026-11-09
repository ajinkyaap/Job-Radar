"""Resume-aligned eligibility checks and transparent job ranking."""

import re

from models import Job


SKILL_GROUPS = {
    "java": (14, ("java", "core java", "j2ee")),
    "spring": (14, ("spring boot", "spring framework", "spring")),
    "microservices": (12, ("microservices", "microservice")),
    "kafka": (12, ("apache kafka", "kafka", "event-driven", "event driven")),
    "rest APIs": (10, ("rest api", "restful api", "api development")),
    "sql databases": (9, ("postgresql", "postgres", "mysql", "sql")),
    "cloud/devops": (8, ("aws", "docker", "kubernetes", "jenkins", "ci/cd")),
    "distributed systems": (8, ("distributed systems", "system design", "concurrency")),
    "banking": (7, ("banking", "financial services", "payments", "fintech")),
    "observability": (6, ("splunk", "grafana", "appdynamics", "production support")),
}

INDIA_LOCATION_TERMS = (
    "india", "pune", "mumbai", "bengaluru", "bangalore", "hyderabad",
    "gurgaon", "gurugram", "noida", "delhi", "chennai", "kolkata",
    "ahmedabad", "kochi", "indore",
)
WORLDWIDE_REMOTE_TERMS = ("worldwide", "global", "anywhere", "distributed", "work from anywhere")
REMOTE_TERMS = ("remote", "remote-first", "work from home", "work remotely")
COUNTRY_TERMS = (
    "us", "usa", "united states", "canada", "uk", "united kingdom", "ireland",
    "europe", "spain", "poland", "germany", "netherlands", "australia", "singapore",
)


def _contains_any(text: str, terms: list[str] | tuple[str, ...]) -> bool:
    return any(term.lower() in text for term in terms)


def _experience_fit(text: str, target_years: float) -> float:
    """Estimate fit from explicit minimum-years requirements; unknown is neutral."""
    requirements = [float(value) for value in re.findall(
        r"(?:minimum of |min\.?\s*)?(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)", text
    )]
    if not requirements:
        return 70
    required = max(requirements)
    if required <= target_years:
        return 100
    if required <= target_years + 1:
        return 70
    return 0


def _location_score(location: str) -> float:
    if any(term in location for term in INDIA_LOCATION_TERMS):
        return 100
    if any(term in location for term in WORLDWIDE_REMOTE_TERMS):
        return 100
    if any(term in location for term in REMOTE_TERMS):
        return 100
    return 20


def calculate(job: Job, profile: dict) -> Job:
    """Score one job and annotate it with a transparent priority and skill evidence."""
    title = (job.title or "").lower()
    location = (job.location or "").lower()
    text = " ".join((title, job.description or "", location)).lower()

    if job.days_old > profile["max_job_age_days"]:
        return _reject(job)

    if location and not _contains_any(location, profile["acceptable_locations"]):
        return _reject(job)

    if _contains_any(title, profile["excluded_title_terms"]):
        return _reject(job)

    if not _contains_any(title, profile["target_title_terms"]):
        return _reject(job)

    experience = _experience_fit(text, float(profile["experience_years"]))
    if experience == 0:
        return _reject(job)

    matched = [name for name, (_, terms) in SKILL_GROUPS.items() if _contains_any(text, terms)]
    skill_score = _skill_coverage_score(len(matched))

    # Metadata used by the digest and Sheets analytics.
    if any(term in location for term in INDIA_LOCATION_TERMS):
        job.role_type = "India"
    elif any(term in location for term in WORLDWIDE_REMOTE_TERMS):
        job.role_type = "Worldwide remote"
    elif any(term in location for term in REMOTE_TERMS):
        job.role_type = "Remote (location restricted)"
    else:
        job.role_type = "Other"
    friction_terms = ("captcha", "assessment", "verification code", "security code", "cover letter required")
    job.application_friction = sum(1 for term in friction_terms if term in text)

    title_score = 100
    location_score = _location_score(location)
    # Freshness is deliberately prominent: competitive roles are most actionable
    # during the first few days after publication.
    freshness_score = (
        100 if job.days_old <= 1 else
        95 if job.days_old <= 3 else
        80 if job.days_old <= 7 else
        55 if job.days_old <= 14 else
        25
    )
    company_score = 100 if job.company.lower() in {c.lower() for c in profile["priority_companies"]} else 60
    final = (
        skill_score * 0.40
        + title_score * 0.15
        + experience * 0.15
        + location_score * 0.05
        + freshness_score * 0.20
        + company_score * 0.05
    )

    final -= min(job.application_friction * 2, 8)

    # A role with only incidental keyword matches is not a high-probability target.
    if len(matched) < profile["minimum_skill_groups"]:
        final -= 20

    job.score = round(min(final, 100), 2)
    job.matched_skills = matched
    job.priority = "HIGH" if job.score >= 80 else "MEDIUM" if job.score >= 65 else "LOW"
    return job


def _reject(job: Job) -> Job:
    job.score = 0
    job.priority = "LOW"
    job.matched_skills = []
    return job


def _skill_coverage_score(groups: int) -> int:
    """Reward several distinct resume matches without requiring every skill."""
    if groups >= 5:
        return 100
    if groups == 4:
        return 85
    if groups == 3:
        return 70
    if groups == 2:
        return 40
    if groups == 1:
        return 15
    return 0
