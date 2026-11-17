"""CareerAlerts India aggregator connector.

CareerAlerts publishes curated listings and exposes the employer's official
application URL on each detail page. We ingest only those public pages and
retain the official link for application.
"""
import re
from datetime import UTC, datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ats.common import html_to_text, is_remote
from models import Job
from utils import calculate_days_old, parse_date


def fetch_careeralerts_jobs(limit=50, timeout=20):
    jobs = []
    try:
        response = requests.get("https://careeralerts.co.in/jobs", headers={"User-Agent": "Mozilla/5.0 JobRadar/1.0"}, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        links = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if href.startswith("/jobs/") and href not in links:
                links.append(href)
        for href in links[:limit]:
            try:
                detail = requests.get(urljoin("https://careeralerts.co.in", href), headers={"User-Agent": "Mozilla/5.0 JobRadar/1.0"}, timeout=timeout)
                detail.raise_for_status()
                page = BeautifulSoup(detail.text, "html.parser")
                text = page.get_text(" ", strip=True)
                title = (page.find("h1").get_text(" ", strip=True) if page.find("h1") else "").replace(" Job", "", 1).strip()
                apply_links = [a.get("href") for a in page.find_all("a", href=True) if "Apply" in a.get_text(" ", strip=True)]
                apply_url = next((u for u in apply_links if u and not u.startswith("#") and "careeralerts.co.in" not in u), detail.url)
                company = ""
                match = re.search(r"Company:\s*([^|]+?)(?:\s+Role:|$)", text)
                if match:
                    company = match.group(1).strip()
                location = "India" if re.search(r"\bIndia\b|Bengaluru|Bangalore|Hyderabad|Pune|Mumbai", text, re.I) else ""
                posted = parse_date((re.search(r"Posted\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", text) or [None, None])[1])
                jobs.append(Job(company=company or "CareerAlerts", title=title, location=location,
                                description=text[:16000], apply_url=apply_url, posted_at=posted,
                                days_old=calculate_days_old(posted), remote=is_remote(text, location),
                                source="CareerAlerts"))
            except requests.RequestException:
                continue
    except requests.RequestException as ex:
        print(f"CareerAlerts error: {type(ex).__name__}")
    print(f"[INFO] CareerAlerts: {len(jobs)} jobs")
    return jobs
