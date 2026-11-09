import re
import yaml
import requests
import smtplib
import gspread

from bs4 import BeautifulSoup

from datetime import datetime
from datetime import timezone
from datetime import timedelta

from typing import Dict
from typing import List
from typing import Set
from typing import Tuple

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.oauth2.service_account import Credentials

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ==========================================================
# CONFIG LOADING
# ==========================================================

CONFIG_FILE = "config.yaml"
BOARDS_FILE = "company_boards.yaml"


def load_yaml(path: str) -> dict:

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_yaml(CONFIG_FILE)
BOARDS = load_yaml(BOARDS_FILE)

MINIMUM_SCORE = CONFIG["minimum_score"]
EXPERIENCE_YEARS = CONFIG["experience_years"]


# ==========================================================
# RESUME PROFILE
# Derived From Resume
# ==========================================================

CORE_SKILLS = {
    "java": 15,
    "spring boot": 15,
    "spring": 10,
    "microservices": 12,
    "kafka": 12,
    "aws": 10,
    "docker": 8,
    "kubernetes": 8,
    "postgresql": 8,
    "mysql": 6,
    "rest api": 8,
    "rest": 5,
    "distributed systems": 10,
    "jenkins": 6,
    "ci/cd": 5,
    "splunk": 4,
    "grafana": 4,
}

SYNONYMS = {
    "spring boot": [
        "spring",
        "springboot"
    ],

    "kafka": [
        "event streaming",
        "messaging",
        "event-driven"
    ],

    "aws": [
        "amazon web services"
    ],

    "rest api": [
        "restful",
        "api development"
    ],

    "microservices": [
        "micro services",
        "service oriented"
    ]
}

TARGET_TITLES = [

    "software engineer",

    "senior software engineer",

    "backend engineer",

    "senior backend engineer",

    "java engineer",

    "java developer",

    "senior java developer",

    "platform engineer",

    "microservices engineer",

    "sde 2",

    "sde ii"
]

DOMAIN_KEYWORDS = [

    "banking",

    "financial services",

    "fintech",

    "payments",

    "capital markets",

    "trading"
]

REMOTE_KEYWORDS = [

    "remote",

    "fully remote",

    "remote-first",

    "work from home",

    "distributed team",

    "anywhere"
]


# ==========================================================
# HTTP SESSION
# ==========================================================

def build_session() -> requests.Session:

    session = requests.Session()

    retries = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=2,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504
        ]
    )

    adapter = HTTPAdapter(
        max_retries=retries
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


SESSION = build_session()


# ==========================================================
# DATE HELPERS
# ==========================================================

def now_utc():

    return datetime.now(timezone.utc)


def parse_date(date_text: str):

    try:

        return datetime.fromisoformat(
            date_text.replace(
                "Z",
                "+00:00"
            )
        )

    except Exception:

        return None


def calculate_days_old(date_text: str) -> int:

    dt = parse_date(date_text)

    if not dt:
        return 999

    return (now_utc() - dt).days


# ==========================================================
# FRESHNESS SCORE
# ==========================================================

def freshness_score(days_old: int) -> int:

    if days_old <= 2:
        return 100

    if days_old <= 7:
        return 80

    if days_old <= 14:
        return 50

    if days_old <= 30:
        return 20

    return 0


# ==========================================================
# EXPERIENCE SCORE
# ==========================================================

def experience_score(job_text: str) -> int:

    job_text = job_text.lower()

    patterns = [

        r"(\d+)\+?\s*years",

        r"(\d+)\s*-\s*(\d+)\s*years"
    ]

    found = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            job_text
        )

        if matches:
            found.extend(matches)

    if not found:
        return 75

    for item in found:

        if isinstance(item, tuple):

            years = int(item[0])

        else:

            years = int(item)

        if years <= 6:
            return 100

        if years <= 8:
            return 80

        if years <= 10:
            return 50

    return 25


# ==========================================================
# SKILL EXTRACTION
# ==========================================================

def extract_skills(text: str):

    text = text.lower()

    found = set()

    for skill in CORE_SKILLS:

        if skill in text:

            found.add(skill)

            continue

        for synonym in SYNONYMS.get(
            skill,
            []
        ):

            if synonym in text:
                found.add(skill)

    return list(found)


def calculate_skill_score(
    text: str
):

    matched_skills = extract_skills(
        text
    )

    possible = sum(
        CORE_SKILLS.values()
    )

    actual = sum(
        CORE_SKILLS[x]
        for x in matched_skills
    )

    percentage = (
        actual / possible
    ) * 100

    return round(
        percentage,
        2
    ), matched_skills


# ==========================================================
# DOMAIN SCORE
# ==========================================================

def domain_score(text: str):

    text = text.lower()

    matches = sum(

        1

        for keyword in DOMAIN_KEYWORDS

        if keyword in text

    )

    if matches >= 2:

        return 100

    if matches == 1:

        return 75

    return 0


# ==========================================================
# TITLE SCORE
# ==========================================================

def title_score(
    title: str
):

    title = title.lower()

    for target in TARGET_TITLES:

        if target in title:
            return 100

    return 20


# ==========================================================
# REMOTE CHECK
# ==========================================================

def is_remote(text: str):

    text = text.lower()

    return any(

        keyword in text

        for keyword in REMOTE_KEYWORDS

    )
# ==========================================================
# GREENHOUSE FETCHER
# ==========================================================

def fetch_greenhouse_jobs(
    board: str
) -> List[Dict]:

    url = (
        f"https://boards-api.greenhouse.io/"
        f"v1/boards/{board}/jobs?content=true"
    )

    try:

        response = SESSION.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        payload = response.json()

        jobs = payload.get(
            "jobs",
            []
        )

        print(
            f"[INFO] {board}: "
            f"{len(jobs)} jobs"
        )

        return jobs

    except Exception as ex:

        print(
            f"[ERROR] Board={board}: {ex}"
        )

        return []


# ==========================================================
# LOCATION HELPERS
# ==========================================================

def location_score(
    location: str
) -> int:

    if not location:
        return 50

    allowed_locations = [
        x.lower()
        for x in CONFIG["locations"]
    ]

    location = location.lower()

    for item in allowed_locations:

        if item in location:
            return 100

    return 50


# ==========================================================
# COMPANY SCORE
# ==========================================================

def company_score(
    company_name: str
):

    priority = set(
        BOARDS.get(
            "priority_companies",
            []
        )
    )

    if company_name in priority:

        return 100

    return 50


# ==========================================================
# PRIORITY
# ==========================================================

def priority_from_score(
    score: float
):

    if score >= 90:
        return "HIGH"

    if score >= 80:
        return "MEDIUM"

    return "LOW"


# ==========================================================
# SCORE ENGINE
# ==========================================================

def calculate_match_score(
    job: Dict
):

    full_text = (
        job["title"]
        + " "
        + job["description"]
    )

    skill_percentage, matched_skills = (
        calculate_skill_score(
            full_text
        )
    )

    role_score = title_score(
        job["title"]
    )

    exp_score = experience_score(
        full_text
    )

    freshness = freshness_score(
        job["days_old"]
    )

    company_points = company_score(
        job["company"]
    )

    final_score = (

        skill_percentage * 0.45

        + role_score * 0.20

        + exp_score * 0.15

        + company_points * 0.10

        + freshness * 0.10
    )

    return {

        "score": round(
            final_score,
            2
        ),

        "matched_skills": matched_skills,

        "domain_score": domain_score(
            full_text
        ),

        "priority": priority_from_score(
            final_score
        )
    }


# ==========================================================
# NORMALIZATION
# ==========================================================

def normalize_job(
    board: str,
    job: Dict
):

    location = ""

    if isinstance(
        job.get("location"),
        dict
    ):

        location = job[
            "location"
        ].get(
            "name",
            ""
        )

    description_html = job.get(
        "content",
        ""
    )

    description = BeautifulSoup(
        description_html,
        "html.parser"
    ).get_text(
        separator=" "
    )

    days_old = calculate_days_old(
        job.get(
            "updated_at",
            ""
        )
    )

    company = board.title()

    return {

        "company": company,

        "title": job.get(
            "title",
            ""
        ),

        "location": location,

        "description": description,

        "apply_url": job.get(
            "absolute_url",
            ""
        ),

        "job_url": job.get(
            "absolute_url",
            ""
        ),

        "posted_at": job.get(
            "updated_at",
            ""
        ),

        "days_old": days_old,

        "remote": is_remote(
            location
            + " "
            + description
        ),

        "source": "Greenhouse"
    }


# ==========================================================
# GOOGLE SHEETS
# ==========================================================

SCOPES = [

    "https://www.googleapis.com/auth/spreadsheets",

    "https://www.googleapis.com/auth/drive"
]


def create_gc():

    credentials = (
        Credentials
        .from_service_account_file(
            CONFIG["google_sheet"][
                "credentials_file"
            ],
            scopes=SCOPES
        )
    )

    return gspread.authorize(
        credentials
    )


def current_sheet_name():

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

    gc = create_gc()

    workbook = gc.open(
        CONFIG["google_sheet"][
            "workbook_name"
        ]
    )

    tab_name = current_sheet_name()

    existing = [
        ws.title
        for ws in workbook.worksheets()
    ]

    if tab_name not in existing:

        ws = workbook.add_worksheet(
            title=tab_name,
            rows=5000,
            cols=20
        )

        headers = [

            "Timestamp",

            "Priority",

            "Match Score",

            "Company",

            "Role",

            "Location",

            "Remote",

            "Posted Date",

            "Freshness",

            "Matched",
            
            "Domain Score",

            "Apply Link",

            "Source",

            "Status",
            
            "Preferred Location"
        ]

        ws.append_row(
            headers
        )

    else:

        ws = workbook.worksheet(
            tab_name
        )

    return workbook, ws


# ==========================================================
# OLD TAB CLEANUP
# ==========================================================

def cleanup_old_tabs(
    workbook
):

    keep_days = CONFIG[
        "delete_tabs_older_than_days"
    ]

    cutoff = (
        datetime.now(UTC)
        - timedelta(
            days=keep_days
        )
    )

    for sheet in workbook.worksheets():

        title = sheet.title

        match = re.match(
            r"(\d{4})_W(\d+)",
            title
        )

        if not match:
            continue

        try:

            year = int(
                match.group(1)
            )

            week = int(
                match.group(2)
            )

            created = (
                datetime
                .fromisocalendar(
                    year,
                    week,
                    1
                )
            )

            if created < cutoff:

                workbook.del_worksheet(
                    sheet
                )

                print(
                    f"[INFO] Deleted "
                    f"{sheet.title}"
                )

        except Exception:

            pass

# ==========================================================
# DEDUPLICATION
# ==========================================================

def build_job_key(job):

    return (
        f"{job['company']}|"
        f"{job['title']}|"
        f"{job['location']}"
    ).lower().strip()


def load_existing_keys(ws):

    records = ws.get_all_records()

    keys = set()

    for row in records:

        company = str(
            row.get("Company", "")
        )

        role = str(
            row.get("Role", "")
        )

        location = str(
            row.get("Location", "")
        )

        key = (
            f"{company}|"
            f"{role}|"
            f"{location}"
        ).lower().strip()

        keys.add(key)

    return keys


# ==========================================================
# GOOGLE SHEET INSERT
# ==========================================================

def insert_jobs(
    worksheet,
    jobs
):

    if not jobs:
        return

    rows = []

    timestamp = datetime.now(UTC).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    for job in jobs:

        rows.append([

            timestamp,

            job["priority"],

            job["score"],

            job["company"],

            job["title"],

            job["location"],

            "YES" if job["remote"] else "NO",

            job["posted_at"],

            job["days_old"],

            ", ".join(
                job["matched_skills"]
            ),

            job["domain_score"],

            job["apply_url"],

            job["source"],

            "NEW"

        ])

    worksheet.append_rows(
        rows,
        value_input_option="RAW"
    )


# ==========================================================
# EMAIL
# ==========================================================

def create_email_html(
    jobs
):

    html = """
    <html>
    <body>
    <h2>Job Radar Alert</h2>
    """

    for job in jobs:

        html += f"""
        <hr>

        <h3>
        {job['company']}
        </h3>

        <b>Role:</b>
        {job['title']}
        <br>

        <b>Score:</b>
        {job['score']}
        <br>

        <b>Priority:</b>
        {job['priority']}
        <br>

        <b>Location:</b>
        {job['location']}
        <br>

        <b>Skills:</b>
        {", ".join(job['matched_skills'])}
        <br>

        <a href="{job['apply_url']}">
        Apply Now
        </a>

        <br><br>
        """

    html += """
    </body>
    </html>
    """

    return html


def send_email(
    jobs
):

    if not jobs:
        print(
            "[INFO] No email required"
        )

        return

    limit = CONFIG[
        "email_top_jobs_limit"
    ]

    jobs = sorted(
        jobs,
        key=lambda x: x["score"],
        reverse=True
    )[:limit]

    sender = CONFIG["email"][
        "sender"
    ]

    password = CONFIG["email"][
        "password"
    ]

    receiver = CONFIG["email"][
        "receiver"
    ]

    msg = MIMEMultipart(
        "alternative"
    )

    msg["Subject"] = (
        f"[Job Radar] "
        f"{len(jobs)} New Matches"
    )

    msg["From"] = sender

    msg["To"] = receiver

    body = create_email_html(
        jobs
    )

    msg.attach(
        MIMEText(
            body,
            "html"
        )
    )

    try:

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465
        ) as smtp:

            smtp.login(
                sender,
                password
            )

            smtp.send_message(
                msg
            )

        print(
            "[INFO] Email sent"
        )

    except Exception as ex:

        print(
            f"[ERROR] Email failed: "
            f"{ex}"
        )


# ==========================================================
# FETCH ALL JOBS
# ==========================================================

def fetch_all_jobs():

    boards = BOARDS.get(
        "greenhouse",
        []
    )

    jobs = []

    for board in boards:

        raw_jobs = (
            fetch_greenhouse_jobs(
                board
            )
        )

        for item in raw_jobs:

            normalized = (
                normalize_job(
                    board,
                    item
                )
            )

            jobs.append(
                normalized
            )

    return jobs


# ==========================================================
# PROCESS JOBS
# ==========================================================

def process_jobs():

    jobs = fetch_all_jobs()

    print(
        f"[INFO] Fetched "
        f"{len(jobs)} jobs"
    )

    matched = set()

    for job in jobs:

        score_info = (
            calculate_match_score(
                job
            )
        )

        job.update(
            score_info
        )

        if (
            job["score"]
            >= MINIMUM_SCORE
        ):

            matched.append(
                job
            )

    print(
        f"[INFO] Matched "
        f"{len(matched)} jobs"
    )

    matched.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return matched


# ==========================================================
# UPDATE GOOGLE SHEET
# ==========================================================

def persist_jobs(
    jobs
):

    workbook, worksheet = (
        get_or_create_sheet()
    )

    cleanup_old_tabs(
        workbook
    )

    existing = (
        load_existing_keys(
            worksheet
        )
    )

    new_jobs = []

    for job in jobs:

        key = build_job_key(
            job
        )

        if key in existing:
            continue

        existing.add(key)

        new_jobs.append(
            job
        )

    insert_jobs(
        worksheet,
        new_jobs
    )

    print(
        f"[INFO] Inserted "
        f"{len(new_jobs)} jobs"
    )

    return new_jobs


# ==========================================================
# MAIN
# ==========================================================

def main():

    print(
        "=" * 60
    )

    print(
        "JOB RADAR STARTED"
    )

    print(
        "=" * 60
    )

    jobs = process_jobs()

    new_jobs = persist_jobs(
        jobs
    )

    send_email(
        new_jobs
    )

    print(
        "=" * 60
    )

    print(
        "JOB RADAR COMPLETE"
    )

    print(
        "=" * 60
    )


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    main()