import requests

from concurrent.futures import (
    ThreadPoolExecutor
)

from ats.common import html_to_text, is_remote, location_text

from models import Job

from utils import (
    calculate_days_old,
    parse_date
)


COMPANY_NAME_MAP = {

    "mongodb": "MongoDB",

    "newrelic": "New Relic",

    "hashicorp": "HashiCorp",

    "cloudflare": "Cloudflare",

    "databricks": "Databricks",

    "okta": "Okta",

    "reddit": "Reddit",

    "stripe": "Stripe",

    "hubspot": "HubSpot"
}


def fetch_board(board):

    url = (
        "https://boards-api.greenhouse.io/"
        f"v1/boards/{board}/jobs"
        "?content=true"
    )

    try:

        response = requests.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        jobs = (
            response
            .json()
            .get("jobs", [])
        )

        print(
            f"[INFO] "
            f"{board}: "
            f"{len(jobs)} jobs"
        )

        return jobs

    except Exception as ex:

        print(
            f"[ERROR] "
            f"{board}: {ex}"
        )

        return []


def normalize_job(
    board,
    job
):

    description = html_to_text(job.get("content"))
    location = location_text(job.get("location"))
    posted_at = job.get("updated_at") or job.get("created_at") or ""

    parsed_posted_at = parse_date(
        posted_at
    )

    days_old = (
        calculate_days_old(
            parsed_posted_at
        )
    )

    company = (
        COMPANY_NAME_MAP.get(
            board,
            board.title()
        )
    )

    remote = is_remote(description, location)

    return Job(

        company=company,

        title=job.get(
            "title",
            ""
        ),

        location=location,

        description=description,

        apply_url=job.get(
            "absolute_url",
            ""
        ),

        posted_at=parsed_posted_at,

        days_old=days_old,

        remote=remote,

        source="Greenhouse"
    )


def fetch_all_jobs(
    boards
):

    jobs = []

    with ThreadPoolExecutor(
        max_workers=10
    ) as executor:

        results = executor.map(
            fetch_board,
            boards
        )

        for board, raw_jobs in zip(
            boards,
            results
        ):

            for job in raw_jobs:

                jobs.append(

                    normalize_job(
                        board,
                        job
                    )

                )

    return jobs
