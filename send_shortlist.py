"""Email the current eligible Sheet shortlist without fetching or applying."""

import argparse
from datetime import datetime

from emailer import send_email
from main import CONFIG, get_or_create_sheet
from models import Job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimum-score", type=float, default=CONFIG.get("minimum_score", 90))
    parser.add_argument("--minimum-remote-score", type=float, default=CONFIG.get("minimum_remote_score", 82))
    parser.add_argument("--limit", type=int, default=CONFIG.get("email_top_jobs_limit", 25))
    args = parser.parse_args()

    worksheet = get_or_create_sheet()
    jobs = []
    seen = set()
    for row in worksheet.get_all_records():
        status = str(row.get("Status", "")).upper()
        url = str(row.get("Apply Link", "")).strip()
        score = float(row.get("Match Score") or 0)
        location = str(row.get("Location", "")).lower()
        is_india = any(term in location for term in ("india", "pune", "mumbai", "bengaluru", "bangalore", "hyderabad", "gurgaon", "gurugram", "noida", "delhi"))
        threshold = args.minimum_score if is_india else args.minimum_remote_score
        if status in {"EXPIRED", "APPLIED"} or score < threshold or not url or url.lower() in seen:
            continue
        seen.add(url.lower())
        posted_text = str(row.get("Posted Date", "")).strip()
        try:
            posted_at = datetime.fromisoformat(posted_text.replace("Z", "+00:00"))
        except ValueError:
            posted_at = None
        skills = [item.strip() for item in str(row.get("Matched Skills", "")).split(",") if item.strip()]
        jobs.append(Job(
            company=str(row.get("Company", "")), title=str(row.get("Role", "")),
            location=str(row.get("Location", "")), description="", apply_url=url,
            posted_at=posted_at, days_old=int(row.get("Days Old") or 999),
            remote=str(row.get("Remote", "")).upper() == "YES", source=str(row.get("Source", "")),
            score=score, matched_skills=skills, priority=str(row.get("Priority", "")),
        ))
    jobs.sort(key=lambda job: job.score, reverse=True)
    jobs = jobs[:max(args.limit, 0)]
    send_email(
        sender=CONFIG["email"]["sender"], password=CONFIG["email"]["password"],
        receiver=CONFIG["email"]["receiver"], jobs=jobs,
    )
    print(f"[INFO] Sent {len(jobs)} application-ready jobs")


if __name__ == "__main__":
    main()
