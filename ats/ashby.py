import requests

from concurrent.futures import ThreadPoolExecutor

from ats.common import html_to_text, is_remote, location_text
from models import Job
from utils import calculate_days_old, parse_date


def fetch_organization_jobs(
    organizations
):

    jobs = []

    for organization in organizations:

        try:

            url = f"https://api.ashbyhq.com/posting-api/job-board/{organization}"

            response = requests.get(
                url,
                timeout=30
            )

            response.raise_for_status()

            for item in response.json().get("jobs", []):
                description = html_to_text(
                    item.get("descriptionHtml") or item.get("descriptionPlain")
                )
                location = location_text(item.get("location"))
                posted_at = parse_date(item.get("publishedAt") or item.get("createdAt"))
                jobs.append(
                    Job(
                        company=organization,
                        title=item.get("title", ""),
                        location=location,
                        description=description,
                        apply_url=item.get("applyUrl") or item.get("jobUrl", ""),
                        posted_at=posted_at,
                        days_old=calculate_days_old(posted_at),
                        remote=is_remote(description, location),
                        source="Ashby"
                    )
                )

        except Exception as ex:
            print(f"Ashby Error {organization}: {ex}")

    return jobs


def fetch_ashby_jobs(organizations):
    """Fetch independent Ashby boards concurrently without one failure stopping a run."""
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(organizations)))) as executor:
        results = executor.map(fetch_organization_jobs, organizations)
        jobs = [job for result in results for job in result]
        print(f"[INFO] Ashby: {len(jobs)} jobs from {len(organizations)} boards")
        return jobs
