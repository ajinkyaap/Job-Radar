from config_loader import load_yaml

from ats.greenhouse import fetch_all_jobs
from ats.lever import fetch_lever_jobs
from ats.ashby import fetch_ashby_jobs
from ats.smartrecruiters import fetch_smartrecruiters_jobs

from matcher import calculate

from emailer import send_email

from sheets import (
    get_client
)

from datetime import datetime
from datetime import UTC


CONFIG = load_yaml("config.yaml")

BOARDS = load_yaml(
    "company_boards.yaml"
)

# ==========================================================
# SHEETS
# ==========================================================

def get_sheet_name():

    week = (
        datetime.now(UTC)
        .isocalendar()
    )

    return (
        f"{week.year}"
        f"_W"
        f"{week.week}"
    )


def get_or_create_sheet():

    client = get_client(
        CONFIG["google_sheet"][
            "credentials_file"
        ]
    )

    workbook = client.open(
        CONFIG["google_sheet"][
            "workbook_name"
        ]
    )

    sheet_name = get_sheet_name()

    existing = [
        ws.title
        for ws in workbook.worksheets()
    ]

    if sheet_name not in existing:

        worksheet = workbook.add_worksheet(
            title=sheet_name,
            rows=5000,
            cols=20
        )

        worksheet.append_row([
            "Timestamp",
            "Priority",
            "Match Score",
            "Company",
            "Role",
            "Location",
            "Location Type",
            "Remote",
            "Posted Date",
            "Days Old",
            "Matched Skills",
            "Source",
            "Apply Link",
            "Status"
        ])

    else:

        worksheet = workbook.worksheet(
            sheet_name
        )

    return worksheet


# ==========================================================
# DEDUPLICATION
# ==========================================================

def build_job_key(job):

    return (
        f"{job.company}|"
        f"{job.title}|"
        f"{job.location}|"
        f"{job.apply_url}"
    ).lower().strip()



def load_existing_keys(
    worksheet
):

    records = (
        worksheet.get_all_records()
    )

    keys = set()

    for row in records:

        key = (
            f"{row.get('Company','')}|"
            f"{row.get('Role','')}|"
            f"{row.get('Location','')}|"
            f"{row.get('Apply Link','')}"
        ).lower().strip()

        keys.add(key)

    return keys


# ==========================================================
# STORE JOBS
# ==========================================================

def persist_jobs(
    worksheet,
    jobs
):

    existing_keys = (
        load_existing_keys(
            worksheet
        )
    )

    inserted_jobs = []

    rows = []

    timestamp = (
        datetime.now(UTC)
        .strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    for job in jobs:

        key = build_job_key(
            job
        )

        if key in existing_keys:
            continue

        existing_keys.add(key)

        inserted_jobs.append(
            job
        )

        location_type = "OTHER"

        job_location = (
            job.location or ""
        ).lower()

        INDIA_LOCATIONS = [
            "india",
            "bangalore",
            "bengaluru",
            "pune",
            "hyderabad",
            "mumbai",
            "navi mumbai",
            "thane",
            "gurgaon",
            "gurugram",
            "noida",
            "delhi",
            "new delhi",
            "chennai",
            "kolkata",
            "ahmedabad",
            "kochi",
            "cochin",
            "trivandrum",
            "bhubaneswar",
            "indore"
        ]

        if any(
            city in job_location
            for city in INDIA_LOCATIONS
        ):
            location_type = "INDIA"

        if any(
            keyword in job_location
            for keyword in [
                "remote",
                "worldwide",
                "global",
                "remote-first"
            ]
        ):
            location_type = "REMOTE"

        rows.append([
            timestamp,
            job.priority,
            job.score,
            job.company,
            job.title,
            job.location,
            location_type,
            "YES"
            if job.remote
            else "NO",
            job.posted_at.isoformat()
            if job.posted_at
            else "",
            job.days_old,
            ",".join(
                job.matched_skills
                or []
            ),
            job.source,
            job.apply_url,
            "NEW"
        ])

    if rows:

        worksheet.append_rows(
            rows,
            value_input_option="RAW"
        )

    print(
        f"[INFO] Added "
        f"{len(inserted_jobs)} "
        f"new jobs"
    )

    return inserted_jobs


# ==========================================================
# FETCH
# ==========================================================

def collect_jobs():

    jobs = []

    greenhouse_boards = (
        BOARDS.get(
            "greenhouse",
            []
        )
    )

    lever_companies = (
        BOARDS.get(
            "lever",
            []
        )
    )

    ashby_companies = (
        BOARDS.get(
            "ashby",
            []
        )
    )
    smartrecruiters_companies = BOARDS.get("smartrecruiters", [])

    print(
        "[INFO] "
        "Fetching Greenhouse jobs..."
    )

    try:
        jobs.extend(fetch_all_jobs(greenhouse_boards))
    except Exception as ex:
        print(f"[ERROR] Greenhouse fetch failed: {ex}")

    print("[INFO] Fetching Lever jobs...")
    try:
        jobs.extend(fetch_lever_jobs(lever_companies))
    except Exception as ex:
        print(f"[ERROR] Lever fetch failed: {ex}")

    print("[INFO] Fetching Ashby jobs...")
    try:
        jobs.extend(fetch_ashby_jobs(ashby_companies))
    except Exception as ex:
        print(f"[ERROR] Ashby fetch failed: {ex}")
    print("[INFO] Fetching SmartRecruiters jobs...")
    try:
        jobs.extend(fetch_smartrecruiters_jobs(smartrecruiters_companies))
    except Exception as ex:
        print(f"[ERROR] SmartRecruiters fetch failed: {ex}")
    unique_jobs = {}

    for job in jobs:

        key = (
            f"{job.company}|"
            f"{job.title}"
        ).lower()

        if key not in unique_jobs:

            unique_jobs[key] = job

    jobs = list(
        unique_jobs.values()
    )

    print(
        f"[INFO] "
        f"Total jobs fetched: "
        f"{len(jobs)}"
    )

    return jobs


# ==========================================================
# SCORE
# ==========================================================

def score_jobs(jobs):

    scored_jobs = []

    minimum_score = (
        CONFIG["minimum_score"]
    )

    remote_score = CONFIG.get(
        "minimum_remote_score",
        minimum_score
    )

    for job in jobs:

        try:

            scored = calculate(job, CONFIG["matching"])

            location_text = (scored.location or "").lower()
            is_india = any(
                term in location_text
                for term in [
                    "india", "pune", "mumbai", "bengaluru", "bangalore",
                    "hyderabad", "gurgaon", "gurugram", "noida", "delhi",
                ]
            )
            threshold = minimum_score if is_india else remote_score

            if scored.score >= threshold:

                print(
                    f"[MATCH] "
                    f"{scored.company} | "
                    f"{scored.title} | "
                    f"{scored.location} | "
                    f"{scored.score:.2f}"
                )

                scored_jobs.append(scored)

        except Exception as ex:

            print(
                f"[ERROR] Scoring failed: {ex}"
            )

    scored_jobs.sort(
        key=lambda x: x.score,
        reverse=True
    )

    return scored_jobs

# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=" * 60)
    print(
        "JOB RADAR STARTED"
    )
    print("=" * 60)

    all_jobs = collect_jobs()
    print(
    f"Collected jobs: "
    f"{len(all_jobs)}"
)

    scored_jobs = score_jobs(
        all_jobs
    )



    worksheet = (
        get_or_create_sheet()
    )

    new_jobs = persist_jobs(
        worksheet,
        scored_jobs
    )

    india_terms = (
        "india", "pune", "mumbai", "bengaluru", "bangalore", "hyderabad",
        "gurgaon", "gurugram", "noida", "delhi", "chennai", "kolkata",
    )
    india_jobs = [
        job for job in scored_jobs
        if any(term in (job.location or "").lower() for term in india_terms)
    ]
    apac_jobs = [job for job in scored_jobs if "apac" in (job.location or "").lower() or "asia pacific" in (job.location or "").lower() or "asia-pacific" in (job.location or "").lower()]
    remote_jobs = [job for job in scored_jobs if job not in india_jobs and job not in apac_jobs]
    section_limit = CONFIG.get("email_maximum_per_section", 25)
    email_jobs = india_jobs[:section_limit] + remote_jobs[:section_limit] + apac_jobs[:section_limit]

    minimum_section = CONFIG.get("email_minimum_per_section", 10)
    if len(india_jobs) < minimum_section:
        print(f"[WARNING] Only {len(india_jobs)} qualifying India jobs; target is {minimum_section}")
    if len(remote_jobs) < minimum_section:
        print(f"[WARNING] Only {len(remote_jobs)} qualifying remote jobs; target is {minimum_section}")
    if len(apac_jobs) < minimum_section:
        print(f"[INFO] Only {len(apac_jobs)} qualifying APAC jobs; this section is optional")

    if email_jobs:

        limit = CONFIG.get(
            "email_top_jobs_limit",
            25
        )

        try:

            send_email(
                sender=CONFIG[
                    "email"
                ]["sender"],

                password=CONFIG[
                    "email"
                ]["password"],

                receiver=CONFIG[
                    "email"
                ]["receiver"],

                jobs=email_jobs
            )

            print(
                f"[INFO] Email sent with {len(email_jobs)} top matches."
            )

        except Exception as ex:

            print(
                f"[WARNING] Email failed: {ex}"
            )

    else:

        print("[INFO] No qualifying jobs found for email.")

    print("=" * 60)

    print(f"Jobs fetched      : {len(all_jobs)}")
    print(f"Jobs matched      : {len(scored_jobs)}")
    print(f"New jobs inserted : {len(new_jobs)}")

    print("=" * 60)

    print("=" * 60)
    print(
        "JOB RADAR COMPLETE"
    )
    print("=" * 60)


if __name__ == "__main__":

    main()
