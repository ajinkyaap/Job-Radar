import requests

from bs4 import BeautifulSoup

from concurrent.futures import (
    ThreadPoolExecutor
)

from models import Job

from utils import (
    calculate_days_old
)


COMPANY_NAME_MAP = {

    "mongodb": "MongoDB",

    "newrelic": "New Relic",

    "hashicorp": "HashiCorp",

    "cloudflare": "Cloudflare"
}


def fetch_board(board):

    url = (
        "https://boards-api.greenhouse.io/"
        f"v1/boards/{board}/jobs?content=true"
    )

    try:

        response = requests.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        return response.json().get(
            "jobs",
            []
        )

    except:

        return []


def normalize(board, job):

    description_html = job.get(
        "content",
        ""
    )

    description = BeautifulSoup(
        description_html,
        "html.parser"
    ).get_text(" ")

    posted_at = (
        job.get("updated_at")
        or job.get("created_at")
        or ""
    )

    days_old = calculate_days_old(
        posted_at
    )

    location = ""

    if isinstance(
        job.get("location"),
        dict
    ):

        location = job[
            "location"
        ].get(
            "name",
            ""
        )

    return Job(
        company=COMPANY_NAME_MAP.get(
            board,
            board.title()
        ),
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
        posted_at=posted_at,
        days_old=days_old,
        remote=False,
        source="Greenhouse"
    )


def fetch_all_jobs(boards):

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

            for item in raw_jobs:

                jobs.append(
                    normalize(
                        board,
                        item
                    )
                )

    return jobs