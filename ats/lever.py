import requests

from ats.common import is_remote
from models import Job
from utils import calculate_days_old, parse_date


def fetch_company_jobs(company):

    url = (
        f"https://api.lever.co/v0/postings/"
        f"{company}?mode=json"
    )

    try:

        response = requests.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        return response.json()

    except Exception as ex:

        print(
            f"Lever Error "
            f"{company}: {ex}"
        )

        return []


def fetch_lever_jobs(companies):

    jobs = []

    for company in companies:

        records = fetch_company_jobs(
            company
        )

        print(f"[INFO] Lever {company}: {len(records)} jobs")

        for record in records:

            text = (
                record.get(
                    "descriptionPlain",
                    ""
                )
                or ""
            )

            location = ""

            if record.get("categories"):

                location = (
                    record["categories"]
                    .get(
                        "location",
                        ""
                    )
                )

            created = (
                record.get(
                    "createdAt"
                )
            )

            posted = parse_date(created)

            days_old = calculate_days_old(
                posted
            )

            jobs.append(
                Job(
                    company=company,
                    title=record.get(
                        "text",
                        ""
                    ),
                    location=location,
                    description=text,
                    apply_url=record.get(
                        "hostedUrl",
                        ""
                    ),
                    posted_at=posted,
                    days_old=days_old,
                    remote=is_remote(text, location),
                    source="Lever"
                )
            )

    return jobs
