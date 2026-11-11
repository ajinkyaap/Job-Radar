"""Resume-aligned eligibility checks and transparent job ranking."""

import re

from models import Job


SKILL_GROUPS = {
    "java": (14, ("java", "core java", "j2ee", "jakarta ee", "jvm", "multithreading", "concurrency")),
    "spring": (14, ("spring boot", "spring framework", "spring cloud", "spring security", "spring mvc", "hibernate")),
    "microservices": (12, ("microservices", "microservice", "distributed services", "service-oriented")),
    "kafka": (12, ("apache kafka", "kafka", "event-driven", "event driven", "rabbitmq", "event streaming")),
    "rest APIs": (10, ("rest api", "restful api", "api development", "web services", "graphql")),
    "sql databases": (9, ("postgresql", "postgres", "mysql", "oracle", "sql", "redis", "dynamodb")),
    "cloud/devops": (8, ("aws", "gcp", "azure", "docker", "kubernetes", "jenkins", "ci/cd", "terraform")),
    "distributed systems": (8, ("distributed systems", "system design", "high availability", "scalability", "resilient")),
    "banking": (7, ("banking", "financial services", "payments", "fintech", "lending", "fraud", "risk", "wallet")),
    "observability": (6, ("splunk", "grafana", "appdynamics", "prometheus", "datadog", "production support", "sre")),
}

INDIA_LOCATION_TERMS = (
    "india", "pune", "mumbai", "bengaluru", "bangalore", "hyderabad",
    "gurgaon", "gurugram", "noida", "delhi", "chennai", "kolkata",
    "ahmedabad", "kochi", "indore",
)
WORLDWIDE_REMOTE_TERMS = ("worldwide", "global", "anywhere", "distributed", "work from anywhere")
APAC_TERMS = ("apac", "asia pacific", "asia-pacific")
ADDITIONAL_TITLE_TERMS = ("payments engineer", "api engineer", "integration engineer", "core services engineer", "distributed systems engineer", "platform developer", "production engineer")
REMOTE_TERMS = ("remote", "remote-first", "work from home", "work remotely")
COUNTRY_TERMS = (
    "us", "usa", "united states", "canada", "uk", "united kingdom", "ireland",
    "europe", "spain", "poland", "germany", "netherlands", "australia", "singapore",
)

REMOTE_COUNTRY_PATTERNS = (
    r"\b(us|usa|united states|canada|uk|united kingdom|ireland|germany|spain|poland|netherlands|australia|singapore)\b",
)


def _contains_any(text: str, terms: list[str] | tuple[str, ...]) -> bool:
    return any(term.lower() in text for term in terms)


def _remote_is_country_restricted(location: str) -> bool:
    """Reject remote labels tied to a country outside the candidate's work region."""
    if not any(term in location for term in REMOTE_TERMS):
        return False
    if any(term in location for term in WORLDWIDE_REMOTE_TERMS):
        return False
    if any(term in location for term in APAC_TERMS):
        return False
    # Bare Remote and Remote - India are allowed; any other qualifier is
    # treated as a geographic restriction (including EMEA/Europe/APAC).
    india = any(term in location for term in INDIA_LOCATION_TERMS)
    bare_remote = location.strip() in {"remote", "remote-first", "work from home", "work remotely"}
    if india or bare_remote:
        return False
    return True


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
    if any(term in location for term in APAC_TERMS):
        return 65
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

    if location and not (_contains_any(location, profile["acceptable_locations"]) or any(term in location for term in APAC_TERMS)):
        return _reject(job)

    if _remote_is_country_restricted(location) and not _contains_any(location, INDIA_LOCATION_TERMS):
        return _reject(job)

    if _contains_any(title, profile["excluded_title_terms"]):
        return _reject(job)

    if not (_contains_any(title, profile["target_title_terms"]) or _contains_any(title, ADDITIONAL_TITLE_TERMS)):
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
    seniority_score = _seniority_fit(text, float(profile["experience_years"]))
    domain_score = 100 if any(term in text for term in ("payments", "banking", "fintech", "financial services", "lending")) else 60
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
        + experience * 0.10
        + seniority_score * 0.05
        + location_score * 0.05
        + freshness_score * 0.20
        + company_score * 0.05
    )

    final -= min(job.application_friction * 2, 8)

    # A role with only incidental keyword matches is not a high-probability target.
    if len(matched) < profile["minimum_skill_groups"]:
        final -= 20

    job.score = round(min(final, 100), 2)
    job.domain_score = domain_score
    job.score_breakdown = {
        "technical_fit": round(skill_score, 1),
        "seniority_fit": round(seniority_score, 1),
        "domain_fit": round(domain_score, 1),
        "location_fit": round(location_score, 1),
        "freshness": round(freshness_score, 1),
    }
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


def _seniority_fit(text: str, target_years: float) -> float:
    if any(term in text for term in ("staff engineer", "principal engineer", "architect", "director", "vice president")):
        return 0
    years = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)", text)]
    if not years:
        return 70
    required = max(years)
    if required <= target_years + 0.5:
        return 100
    if required <= target_years + 1.5:
        return 75
    if required <= target_years + 2.5:
        return 45
    return 0
