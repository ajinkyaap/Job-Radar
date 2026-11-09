CORE_SKILLS = {
    "java": 15,
    "spring boot": 15,
    "spring framework": 12,
    "spring": 10,
    "kafka": 12,
    "apache kafka": 12,
    "microservices": 12,
    "aws": 10,
    "amazon web services": 10,
    "docker": 8,
    "kubernetes": 8,
    "postgresql": 8,
    "postgres": 8,
    "mysql": 6,
    "distributed systems": 10,
    "event driven": 8,
    "event-driven": 8,
    "rest api": 8,
    "restful api": 8,
    "jenkins": 6,
    "ci/cd": 5,
    "sql": 5,
    "jwt": 4,
    "banking": 10,
    "financial services": 10,
}

POSITIVE_TITLES = [
    "software engineer",
    "senior software engineer",
    "software developer",
    "backend engineer",
    "backend developer",
    "java engineer",
    "java developer",
    "platform engineer",
    "application engineer",
    "staff engineer",
    "site reliability engineer",
    "sre",
    "microservices engineer",
]

NEGATIVE_TITLES = [
    "architect",
    "pre-sales",
    "presales",
    "sales",
    "consultant",
    "advisory",
    "partner",
    "customer success",
]

EXCLUDED_KEYWORDS = [
    "intern",
    "internship",
    "new grad",
    "graduate",
    "campus",
    "student",
]

PRIORITY_COMPANIES = [
    "Databricks",
    "Stripe",
    "MongoDB",
    "Cloudflare",
    "Coinbase",
    "Reddit",
    "Elastic",
    "Okta",
    "Affirm",
    "Lyft",
]

LEADERSHIP_KEYWORDS = [
    "director",
    "vp",
    "vice president",
    "head of",
]

INDIA_LOCATIONS = [

    "india",

    "bangalore",
    "bengaluru",

    "pune",

    "hyderabad",

    "mumbai",

    "navi mumbai",

    "thane",

    "gurgaon",

    "gurugram",

    "noida",

    "delhi",

    "new delhi",

    "chennai",

    "kolkata",

    "ahmedabad",

    "kochi",

    "cochin",

    "trivandrum",

    "bhubaneswar",

    "indore"
]


REMOTE_LOCATIONS = [

    "remote",

    "worldwide",

    "global",

    "remote-first",

    "work from home",

    "work remotely",

    "distributed"
]

MAX_JOB_AGE = 30

def location_score(location):

    location = (
        location or ""
    ).lower()

    # Worldwide remote gets highest score

    for keyword in REMOTE_LOCATIONS:

        if keyword in location:

            return 100

    # India gets highest score

    for city in INDIA_LOCATIONS:

        if city in location:

            return 100

    # Unknown location

    if not location.strip():

        return 50

    # Foreign onsite

    return 10

def location_score(location):

    location = (
        location or ""
    ).lower()

    preferred = [

        "remote",

        "worldwide",

        "global",

        "india"
    ]

    for item in preferred:

        if item in location:
            return 100

    return 20

def freshness_score(days):

    if days <= 2:
        return 100

    if days <= 7:
        return 80

    if days <= 14:
        return 50

    if days <= 30:
        return 20

    return 0


def company_score(company):

    if company in PRIORITY_COMPANIES:
        return 100

    return 50


def title_score(title):

    title = title.lower()

    for keyword in POSITIVE_TITLES:

        if keyword in title:
            return 100

    for keyword in NEGATIVE_TITLES:

        if keyword in title:
            return 20

    return 50


def experience_score(text):

    text = text.lower()

    if "10+ years" in text:
        return 30

    if "8+ years" in text:
        return 50

    if "6+ years" in text:
        return 80

    if "5+ years" in text:
        return 90

    if "4+ years" in text:
        return 100

    return 75


def calculate(job):

    title = (job.title or "").lower()

    if job.days_old > MAX_JOB_AGE:

        job.score = 0
        job.priority = "LOW"
        job.matched_skills = []

        return job
    
    location = (
        job.location or ""
    ).lower()

    allowed = [

        "remote",

        "india",

        "worldwide",

        "global"
    ]

    if location:

        found = False

        for item in allowed:

            if item in location:

                found = True
                break

        if not found:

            job.score = 0
            job.priority = "LOW"
            job.matched_skills = []

            return job

    for keyword in EXCLUDED_KEYWORDS:

        if keyword in title:

            job.score = 0
            job.priority = "LOW"
            job.matched_skills = []

            return job
        
    for keyword in LEADERSHIP_KEYWORDS:
        if keyword in title:

            job.score = 0

            job.priority = "LOW"

            return job
    text = (
        (job.title or "")
        + " "
        + (job.description or "")
        + " "
        + (job.location or "")
    ).lower()

    matched = set()

    total_weight = sum(
        CORE_SKILLS.values()
    )

    actual_weight = 0

    for skill, weight in CORE_SKILLS.items():

        if skill in text:

            matched.add(skill)
            actual_weight += weight

    skill_score = (
        actual_weight / total_weight
    ) * 100

    title_points = title_score(
        job.title
    )

    company_points = company_score(
        job.company
    )

    experience_points = experience_score(
        text
    )

    location_points = location_score(
        job.location
    )

    freshness = freshness_score(
        job.days_old
    )

    final = (
        skill_score * 0.35
        + title_points * 0.20
        + company_points * 0.10
        + experience_points * 0.15
        + freshness * 0.10
        + location_points * 0.10
    )

    if job.company in PRIORITY_COMPANIES:
        final += 5

    if "backend" in title:
        final += 10

    if "software engineer" in title:
        final += 10

    if "java" in title:
        final += 10

    if "platform engineer" in title:
        final += 5

    if "staff engineer" in title:
        final -= 10

    if "principal" in title:
        final -= 15

    if "director" in title:
        final -= 30

    final = min(
        round(final, 2),
        100
    )

    job.score = final

    job.matched_skills = sorted(
        list(matched)
    )

    if final >= 90:
        job.priority = "HIGH"
    elif final >= 80:
        job.priority = "MEDIUM"
    else:
        job.priority = "LOW"

    return job