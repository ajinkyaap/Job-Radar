"""Jooble public jobs API connector."""
import os
from datetime import UTC, datetime, timedelta
import requests
from ats.common import is_remote
from models import Job

def fetch_jooble_jobs(queries, max_results=20):
    key = os.getenv("JOOBLE_API_KEY")
    if not key:
        print("[INFO] Jooble skipped: JOOBLE_API_KEY not configured")
        return []
    jobs = []
    for query in queries:
        try:
            response = requests.post(f"https://jooble.org/api/{key}", json={"keywords": query.get("keywords", ""), "location": query.get("location", "India"), "page": 1}, headers={"Content-Type": "application/json", "User-Agent": "JobRadar/1.0"}, timeout=30)
            response.raise_for_status()
            items = response.json().get("jobs", [])[:max_results]
            print(f"[INFO] Jooble {query.get('location', 'India')} / {query.get('keywords', '')}: {len(items)} jobs")
            for item in items:
                location = item.get("location", "") or query.get("location", "India")
                description = item.get("snippet", "") or ""
                jobs.append(Job(company=item.get("company", "Unknown company"), title=item.get("title", ""), location=location, description=description, apply_url=item.get("link", ""), posted_at=datetime.now(UTC) - timedelta(days=1), days_old=1, remote=is_remote(description, location), source="Jooble"))
        except requests.RequestException as ex:
            print(f"Jooble Error ({query.get('keywords', '')}): {ex}")
    print(f"[INFO] Jooble: {len(jobs)} candidate jobs")
    return jobs
