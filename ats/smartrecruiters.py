"""SmartRecruiters public postings API client."""
import requests

from ats.common import html_to_text, is_remote, location_text
from models import Job
from utils import calculate_days_old, parse_date


def fetch_smartrecruiters_jobs(companies):
    jobs = []
    for company in companies:
        try:
            postings = []
            offset = 0
            page_size = 100
            while True:
                url = f"https://api.smartrecruiters.com/v1/companies/{company}/postings?limit={page_size}&offset={offset}"
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                payload = response.json()
                page = payload.get("content", [])
                postings.extend(page)
                total = int(payload.get("totalFound", len(postings)) or len(postings))
                if not page or len(postings) >= total or len(page) < page_size:
                    break
                offset += page_size
            print(f"[INFO] SmartRecruiters {company}: {len(postings)} jobs")
            for item in postings:
                loc = location_text(item.get("location"))
                posted = parse_date(item.get("releasedDate") or item.get("updatedDate"))
                description = html_to_text(item.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", ""))
                jobs.append(Job(company=company, title=item.get("name", ""), location=loc, description=description, apply_url=item.get("ref", ""), posted_at=posted, days_old=calculate_days_old(posted), remote=is_remote(description, loc), source="SmartRecruiters"))
        except Exception as ex:
            print(f"SmartRecruiters Error {company}: {ex}")
    return jobs
