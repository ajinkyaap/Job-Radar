"""Public Oracle Recruiting Cloud (Candidate Experience) connector."""
from urllib.parse import quote

import requests

from ats.common import html_to_text, is_remote
from models import Job
from utils import calculate_days_old, parse_date


def fetch_oracle_jobs(boards, timeout=30):
    jobs = []
    for board in boards or []:
        company, host, site = (board.get(k, "") for k in ("company", "host", "site"))
        if not host or not site:
            continue
        url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        try:
            response = requests.get(url, params={
                "onlyData": "true",
                "expand": "requisitionList.secondaryLocations",
                "finder": f'findReqs;siteNumber={site},limit=100,offset=0,sortBy=POSTING_DATES_DESC',
            }, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 JobRadar/1.0"}, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            block = (payload.get("items") or [{}])[0]
            postings = block.get("requisitionList", [])
            print(f"[INFO] Oracle {company}: {len(postings)} jobs")
            for item in postings:
                job_id = str(item.get("Id") or item.get("RequisitionId") or "")
                location = item.get("PrimaryLocation") or item.get("PrimaryLocationCountry") or ""
                description = html_to_text(item.get("ShortDescriptionStr") or item.get("Description") or "")
                apply_url = f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{quote(job_id)}"
                posted = parse_date(item.get("PostedDate"))
                jobs.append(Job(company=company, title=item.get("Title", ""), location=location,
                                description=description, apply_url=apply_url, posted_at=posted,
                                days_old=calculate_days_old(posted),
                                remote=is_remote(item.get("WorkplaceType"), description, location),
                                source="Oracle Cloud"))
        except Exception as ex:
            print(f"Oracle Error {company}: {type(ex).__name__}")
    return jobs
