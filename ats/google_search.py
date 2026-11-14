"""Optional Google Programmable Search discovery source.

This uses Google's JSON API rather than scraping search-result HTML. Results
are deliberately limited to career/job URLs and still pass through matcher.py.
"""
import os
import re
from datetime import UTC, datetime, timedelta

import requests
from bs4 import BeautifulSoup

from ats.common import html_to_text, is_remote
from models import Job


JOB_URL_RE = re.compile(r"/(jobs?|careers?|job-detail|jobdetails|posting)([/_?=-]|$)|jobs\.(lever|ashby)\.co|greenhouse\.io|myworkdayjobs\.com|smartrecruiters\.com", re.I)


def _age_from_result(item: dict) -> tuple[datetime, int]:
    text = str((item.get("pagemap") or {}).get("metatags", [{}])[0].get("article:published_time", ""))
    try:
        posted = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return posted, max(0, (datetime.now(UTC) - posted).days)
    except (ValueError, TypeError):
        # Google usually omits dates for career pages; use a neutral age rather
        # than falsely claiming the result was posted today.
        return datetime.now(UTC) - timedelta(days=7), 7


def fetch_google_jobs(queries: list[str], max_results: int = 10) -> list[Job]:
    key, cx = os.getenv("GOOGLE_SEARCH_API_KEY"), os.getenv("GOOGLE_SEARCH_CX")
    if not key or not cx:
        print("[INFO] Google discovery skipped: GOOGLE_SEARCH_API_KEY/CX not configured")
        return []
    jobs = []
    for query in queries:
        try:
            response = requests.get("https://www.googleapis.com/customsearch/v1", params={"key": key, "cx": cx, "q": query, "num": min(max_results, 10)}, timeout=20)
            response.raise_for_status()
            for item in response.json().get("items", []):
                url = item.get("link", "")
                if not JOB_URL_RE.search(url):
                    continue
                page_text = item.get("snippet", "")
                try:
                    page = requests.get(url, timeout=12, headers={"User-Agent": "JobRadar/1.0"})
                    if page.ok:
                        page_text = html_to_text(BeautifulSoup(page.text, "html.parser").get_text(" ", strip=True))[:12000]
                except requests.RequestException:
                    pass
                title = item.get("title", "")
                company = (url.split("//", 1)[-1].split("/", 1)[0]).replace("www.", "")
                posted, age = _age_from_result(item)
                location = "India" if re.search(r"\bindia\b|bengaluru|bangalore|hyderabad|pune|mumbai", query, re.I) else "Remote" if re.search(r"\bremote\b|worldwide", query, re.I) else ""
                jobs.append(Job(company=company, title=title, location=location, description=page_text, apply_url=url, posted_at=posted, days_old=age, remote=is_remote(page_text, location), source="Google Jobs"))
        except requests.RequestException as ex:
            # Do not print the exception URL: requests includes the `key`
            # query parameter, which would leak the Google API credential.
            status = getattr(getattr(ex, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            print(f"Google discovery error for configured query{suffix}")
            if status in {401, 403}:
                print("[WARNING] Google discovery disabled for this run; check API access, key restrictions, and CX.")
                break
    print(f"[INFO] Google discovery: {len(jobs)} candidate pages")
    return jobs
