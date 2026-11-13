"""Eightfold PCS-X public careers search connector.

Eightfold-hosted career sites expose a public, paginated search endpoint. Each
board is configured with the tenant host (for example ``microsoft.eightfold.ai``)
and the employer domain used by the endpoint.
"""

from datetime import UTC, datetime
from urllib.parse import urlencode

import requests

from ats.common import html_to_text, is_remote, location_text
from models import Job
from utils import calculate_days_old


def _posted_at(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value, UTC)
    return None


def fetch_eightfold_jobs(boards, timeout=30):
    jobs = []
    for board in boards or []:
        company = board.get("company", "Eightfold")
        host = board.get("host", "").strip().rstrip("/")
        domain = board.get("domain", "").strip()
        if not host or not domain:
            print(f"[WARNING] Eightfold {company}: missing host or domain")
            continue
        params = {"domain": domain, "query": "", "location": "", "start": 0}
        try:
            response = requests.get(
                f"https://{host}/api/pcsx/search?{urlencode(params)}",
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 JobRadar/1.0"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            positions = (payload.get("data") or {}).get("positions", [])
            print(f"[INFO] Eightfold {company}: {len(positions)} jobs")
            for item in positions:
                location = location_text(item.get("locations") or item.get("location"))
                description = html_to_text(item.get("description") or item.get("jobDescription") or "")
                posted = _posted_at(item.get("postedTs") or item.get("postedTimestamp"))
                apply_url = item.get("positionUrl") or item.get("url") or ""
                if apply_url.startswith("/"):
                    apply_url = f"https://{host}{apply_url}"
                jobs.append(Job(
                    company=company,
                    title=item.get("name") or item.get("title") or "",
                    location=location,
                    description=description,
                    apply_url=apply_url,
                    posted_at=posted,
                    days_old=calculate_days_old(posted),
                    remote=is_remote(item.get("workLocationOption"), description, location),
                    source="Eightfold",
                ))
        except Exception as ex:
            print(f"Eightfold Error {company}: {ex}")
    return jobs
