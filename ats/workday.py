"""Workday public career-site CXS connector.

Each Workday customer has a different tenant, data-centre, and site name.
Entries are configured as {company, host, tenant, site} in workday_boards.yaml.
"""
import requests

from ats.common import html_to_text, is_remote, location_text
from models import Job
from utils import calculate_days_old, parse_date


def fetch_workday_jobs(boards):
    jobs = []
    for board in boards:
        company, host, tenant, site = (board.get(k, "") for k in ("company", "host", "tenant", "site"))
        url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
        try:
            response = requests.post(url, json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}, headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0 JobRadar/1.0"}, timeout=30)
            response.raise_for_status()
            payload = response.json()
            postings = payload.get("jobPostings", [])
            print(f"[INFO] Workday {company}: {len(postings)} jobs")
            for item in postings:
                location = item.get("locationsText") or location_text(item.get("locations"))
                title = item.get("title", "")
                description = html_to_text(" ".join(item.get("bulletFields", []) or []))
                external = item.get("externalPath", "")
                apply_url = f"https://{host}{external}" if external.startswith("/") else external
                posted = parse_date(item.get("postedOn") or item.get("startDate"))
                jobs.append(Job(company=company, title=title, location=location, description=description, apply_url=apply_url, posted_at=posted, days_old=calculate_days_old(posted), remote=is_remote(description, location), source="Workday"))
        except Exception as ex:
            print(f"Workday Error {company}: {ex}")
    return jobs
