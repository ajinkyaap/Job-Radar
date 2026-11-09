"""Low-interaction application assistant for Job Radar matches.

It supports common Greenhouse, Lever, and Ashby fields. By default it only
prefills forms and records items requiring review. Submission is opt-in and
fails closed whenever a required field, CAPTCHA, or consent screen is unclear.
"""

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from config_loader import load_yaml
from sheets import get_client


STATUS_COLUMN = 14
NOTES_COLUMN = 15
PROFILE_FILE = "application_profile.yaml"
QUEUE_FILE = "application_queue.json"
CAPTCHA_MARKERS = ("captcha", "recaptcha", "hcaptcha", "verify you are human")
EXPIRED_MARKERS = (
    "job not found",
    "job is expired",
    "job has expired",
    "job expired",
    "posting is expired",
    "this posting has expired",
    "position is no longer available",
    "this job is no longer available",
    "this position has been filled",
    "no longer accepting applications",
    "applications are closed",
    "applications for this position are closed",
    "we couldn't find the job",
)
INDIA_LOCATION_TERMS = (
    "india", "pune", "mumbai", "bengaluru", "bangalore", "hyderabad",
    "gurgaon", "gurugram", "noida", "delhi", "chennai", "kolkata",
    "ahmedabad", "kochi", "indore",
)


def current_sheet_name() -> str:
    week = datetime.now(UTC).isocalendar()
    return f"{week.year}_W{week.week}"


def get_worksheet(config: dict):
    client = get_client(config["google_sheet"]["credentials_file"])
    workbook = client.open(config["google_sheet"]["workbook_name"])
    return workbook.worksheet(current_sheet_name())


def queue_jobs(worksheet, minimum_score: float, include_review: bool = False, retry_captcha: bool = False) -> list[dict]:
    jobs = []
    seen_urls = set()
    for row_number, row in enumerate(worksheet.get_all_records(), start=2):
        status = str(row.get("Status", "")).upper()
        note = str(row.get("Application Notes", ""))
        score = float(row.get("Match Score") or 0)
        # Retry prefilled forms in submit mode; review-only items remain out of
        # automatic batches until their missing answer is supplied by the user.
        statuses = {"NEW", "PREFILLED"}
        if include_review:
            statuses.add("NEEDS_REVIEW")
        if status == "NEEDS_REVIEW" and "captcha" in note.lower() and not retry_captcha:
            continue
        apply_url = str(row.get("Apply Link", "")).strip()
        if status in statuses and score >= minimum_score and apply_url:
            if apply_url.lower() in seen_urls:
                continue
            seen_urls.add(apply_url.lower())
            jobs.append({
                "row_number": row_number,
                "company": row.get("Company", ""),
                "title": row.get("Role", ""),
                "location": row.get("Location", ""),
                "score": score,
                "apply_url": apply_url,
                "source": row.get("Source", ""),
                "status": status,
            })
    return sorted(
        jobs,
        key=lambda job: (job["status"] != "PREFILLED", -job["score"]),
    )


def write_queue(jobs: list[dict]) -> None:
    Path(QUEUE_FILE).write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    print(f"[INFO] Wrote {len(jobs)} eligible jobs to {QUEUE_FILE}")


def _fill_first(locator, value: str) -> bool:
    if not value or locator.count() == 0:
        return False
    try:
        locator.first.fill(value)
        return True
    except Exception:
        return False


def _answer_choice(page, question_pattern: str, answer: str) -> None:
    """Select a known answer inside the matching form question, when possible."""
    for index in range(page.locator("fieldset").count()):
        fieldset = page.locator("fieldset").nth(index)
        try:
            if not re.search(question_pattern, fieldset.inner_text(), re.I):
                continue
            choice = fieldset.get_by_label(re.compile(f"^{re.escape(answer)}$", re.I))
            if choice.count():
                element = choice.first
                tag_name = element.evaluate("node => node.tagName").lower()
                if tag_name == "select":
                    element.select_option(label=answer)
                elif (element.get_attribute("type") or "").lower() in {"radio", "checkbox"}:
                    element.check()
                else:
                    element.fill(answer)
                return
        except Exception:
            continue


def eligibility_for_location(location: str, profile: dict) -> dict:
    """Select the truthful eligibility policy for the job's stated location."""
    eligibility = profile.get("eligibility", {})
    location = (location or "").lower()
    policy_name = "india" if any(term in location for term in INDIA_LOCATION_TERMS) else "other_countries"
    return eligibility.get(policy_name, {})


def fill_standard_fields(page, profile: dict, job: dict) -> None:
    """Fill only common, non-sensitive fields; unknown questions are untouched."""
    identity = profile["identity"]
    fields = {
        r"first.?name|given.?name": identity.get("first_name", ""),
        r"last.?name|family.?name|surname": identity.get("last_name", ""),
        r"e-?mail": identity.get("email", ""),
        r"phone|mobile": identity.get("phone", ""),
        r"city": identity.get("city", ""),
        r"country": identity.get("country", ""),
        r"linkedin": identity.get("linkedin_url", ""),
        r"website|portfolio": identity.get("website_url", ""),
        r"notice|availability": profile.get("notice_period", ""),
    }
    for label, value in fields.items():
        _fill_first(page.get_by_label(re.compile(label, re.I)), value)

    resume = profile.get("resume_file", "")
    if resume and Path(resume).is_file():
        try:
            page.locator("input[type=file]").first.set_input_files(resume)
        except Exception:
            pass

    answers = profile.get("custom_answers", {})
    for label, value in answers.items():
        _fill_first(page.get_by_label(re.compile(re.escape(label), re.I)), str(value))

    eligibility = eligibility_for_location(job.get("location", ""), profile)
    _answer_choice(page, r"authori[sz]ed to work", eligibility.get("work_authorization", ""))
    _answer_choice(page, r"require.*sponsor", eligibility.get("requires_sponsorship", ""))


def unanswered_required_fields(page) -> list[str]:
    required = page.locator(
        "input[required], textarea[required], select[required], "
        "input[aria-required=true], textarea[aria-required=true], select[aria-required=true]"
    )
    checked_radio_groups = set()
    missing = []
    for index in range(required.count()):
        field = required.nth(index)
        try:
            if not field.is_visible():
                continue
            field_type = (field.get_attribute("type") or "").lower()
            if field_type == "radio":
                group = field.get_attribute("name") or str(index)
                if group in checked_radio_groups:
                    continue
                checked_radio_groups.add(group)
                if page.locator(f'input[type="radio"][name="{group}"]:checked').count() == 0:
                    missing.append(group)
            elif field_type == "checkbox" and not field.is_checked():
                name = field.get_attribute("name") or "required checkbox"
                missing.append("email verification code" if "security-input" in name else name)
            elif field_type not in {"radio", "checkbox"} and not field.input_value().strip():
                name = field.get_attribute("name") or field.get_attribute("id") or "required field"
                missing.append("email verification code" if "security-input" in name else name)
        except Exception:
            missing.append("unreadable required field")
    return missing


def requires_human_check(page) -> bool:
    selector = "iframe[src*=recaptcha], iframe[src*=hcaptcha], .g-recaptcha, .h-captcha"
    widgets = page.locator(selector)
    for index in range(widgets.count()):
        try:
            if widgets.nth(index).is_visible():
                return True
        except Exception:
            return True
    return False


def request_verification_code(page) -> bool:
    """Ask the form to send a fresh email code when it exposes that action."""
    controls = page.get_by_role(
        "button", name=re.compile(r"send(?: verification)? code|email code|verify email", re.I)
    )
    if controls.count() == 0:
        controls = page.get_by_role(
            "link", name=re.compile(r"send(?: verification)? code|email code|verify email", re.I)
        )
    for index in range(controls.count()):
        try:
            if controls.nth(index).is_visible():
                controls.nth(index).click()
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue
    return False


def enter_verification_code(page, code: str) -> bool:
    """Fill common Greenhouse OTP input layouts and verify they contain values."""
    selectors = (
        'input[name^="security-input"]',
        'input[id^="security-input"]',
        'input[autocomplete="one-time-code"]',
        'input[inputmode="numeric"]',
    )
    fields = None
    for selector in selectors:
        candidate = page.locator(selector)
        if candidate.count():
            fields = candidate
            break
    if fields is None:
        return False
    if fields.count() == 1:
        fields.first.fill(code)
    elif fields.count() >= len(code):
        for index, digit in enumerate(code):
            fields.nth(index).fill(digit)
    else:
        # Some Greenhouse forms expose a fixed group of fewer inputs but still
        # accept the complete code in the first field.
        fields.first.fill(code)
    page.wait_for_timeout(300)
    return any(
        fields.nth(index).input_value().strip()
        for index in range(fields.count())
    )


def expired_reason(page, response) -> str:
    """Return a reason when the board says a posting is closed or missing."""
    if response and response.status >= 400:
        return f"Job board returned HTTP {response.status}"
    try:
        text = page.locator("body").inner_text().lower()
    except Exception:
        return "Unable to verify job-page availability"
    for marker in EXPIRED_MARKERS:
        if marker in text:
            return f"Job board reports: {marker}"
    # Some ATS banners only say "Expired" without the surrounding sentence.
    if re.search(r"\bexpired\b", text):
        return "Job board page contains an expired-posting banner"
    return ""


def open_application_form(page, context):
    """Open the ATS application form when the job page has an Apply CTA."""
    submit_controls = page.locator('button[type="submit"], input[type="submit"]')
    if submit_controls.count() or page.get_by_role("button", name=re.compile(r"submit application|submit", re.I)).count():
        return page
    apply_cta = page.get_by_role("link", name=re.compile(r"apply(?: now| for this job)?", re.I))
    if apply_cta.count() == 0:
        apply_cta = page.get_by_role("button", name=re.compile(r"apply(?: now| for this job)?", re.I))
    if apply_cta.count():
        existing_pages = set(context.pages)
        clicked = False
        for index in range(apply_cta.count()):
            candidate = apply_cta.nth(index)
            try:
                if candidate.is_visible():
                    candidate.click()
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            return page
        page.wait_for_timeout(1500)
        new_pages = [candidate for candidate in context.pages if candidate not in existing_pages]
        if new_pages:
            form_page = new_pages[-1]
            form_page.wait_for_load_state("domcontentloaded", timeout=20_000)
            form_page.set_default_timeout(8_000)
            return form_page
    return page


def find_application_surface(page):
    """Return the page or embedded frame that contains the actual form."""
    surfaces = [page, *page.frames]
    for surface in surfaces:
        try:
            if (
                surface.locator('button[type="submit"], input[type="submit"]').count()
                or surface.get_by_label(re.compile(r"e-?mail", re.I)).count()
            ):
                return surface
        except Exception:
            continue
    return page


def greenhouse_fallback_url(job: dict) -> str | None:
    """Recover the canonical Greenhouse form from custom career-site links."""
    match = re.search(r"[?&]gh_jid=(\d+)", job.get("apply_url", ""))
    if not match or job.get("source") != "Greenhouse":
        return None
    slug = re.sub(r"[^a-z0-9]+", "", job.get("company", "").lower())
    return f"https://boards.greenhouse.io/{slug}/jobs/{match.group(1)}"


def no_application_action_reason(page) -> str:
    """Detect a loaded job shell that has no live application action."""
    submit_controls = page.locator('button[type="submit"], input[type="submit"]')
    if submit_controls.count() or page.get_by_role("button", name=re.compile(r"submit application|submit", re.I)).count():
        return ""
    apply_cta = page.get_by_role("link", name=re.compile(r"apply(?: now| for this job)?", re.I))
    if apply_cta.count() == 0:
        apply_cta = page.get_by_role("button", name=re.compile(r"apply(?: now| for this job)?", re.I))
    return "No live application form or Apply action found" if apply_cta.count() == 0 else ""


def submit_if_safe(page, allow_submit: bool, wait_for_code: bool = False) -> tuple[str, str]:
    missing = unanswered_required_fields(page)
    if wait_for_code and "email verification code" in missing:
        print("[INFO] Coinbase verification fields detected")
        request_verification_code(page)
        print("[INFO] Waiting up to 120 seconds for the latest Gmail verification code...")
        try:
            from gmail_reader import get_latest_verification_code
            for _ in range(24):
                code = get_latest_verification_code(max_age_minutes=60)
                if code:
                    if enter_verification_code(page, code):
                        print("[INFO] Verification code entered from Gmail")
                    else:
                        return "NEEDS_REVIEW", "Verification code fields were not writable"
                page.wait_for_timeout(5_000)
                if code:
                    break
        except Exception as error:
            return "NEEDS_REVIEW", f"Gmail verification reader unavailable: {error}"
        missing = unanswered_required_fields(page)
    if requires_human_check(page):
        return "NEEDS_REVIEW", "CAPTCHA or human-verification widget detected"
    if missing:
        return "NEEDS_REVIEW", f"Required fields not completed: {', '.join(missing[:5])}"
    if not allow_submit:
        return "PREFILLED", "Standard fields completed; ready for optional submission"

    buttons = page.locator('button[type="submit"], input[type="submit"]')
    if buttons.count() == 0:
        buttons = page.get_by_role("button", name=re.compile(r"submit application|submit", re.I))
    if buttons.count() == 0:
        return "NEEDS_REVIEW", "Submit button was not found"
    buttons.first.click()
    page.wait_for_timeout(3000)
    confirmation = page.locator("body").inner_text().lower()
    if "thank" in confirmation or "application received" in confirmation or "application submitted" in confirmation:
        return "APPLIED", "Submission confirmation detected"
    missing = unanswered_required_fields(page)
    if missing:
        return "NEEDS_REVIEW", f"Form validation requires: {', '.join(missing[:5])}"
    return "NEEDS_REVIEW", "Submission was not confirmed by the job board"


def update_job_status(worksheet, row_number: int, status: str, note: str) -> None:
    """Persist a concise application outcome and diagnostic note in the sheet."""
    headers = worksheet.row_values(1)
    if len(headers) < NOTES_COLUMN or headers[NOTES_COLUMN - 1] != "Application Notes":
        worksheet.update_cell(1, NOTES_COLUMN, "Application Notes")
    worksheet.update_cell(row_number, STATUS_COLUMN, status)
    worksheet.update_cell(row_number, NOTES_COLUMN, note)


def process_jobs(jobs: list[dict], profile: dict, worksheet, allow_submit: bool, prune_expired: bool = False, wait_for_code: bool = False) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit(
            "Playwright is not installed. Run `python -m pip install -r requirements.txt` "
            "and `python -m playwright install chromium`."
        ) from error

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            ".job-radar-browser", headless=False
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(8_000)
        for job in jobs:
            print(f"[INFO] Opening {job['company']} | {job['title']}")
            try:
                landing_url = greenhouse_fallback_url(job) or job["apply_url"]
                response = page.goto(
                    landing_url, wait_until="commit", timeout=20_000
                )
                expired = expired_reason(page, response)
                if expired:
                    status, note = "EXPIRED", expired
                elif prune_expired:
                    unavailable = no_application_action_reason(page)
                    status, note = ("EXPIRED", unavailable) if unavailable else (job["status"], "Job page and Apply action are available")
                else:
                    form_page = open_application_form(page, context)
                    form_surface = find_application_surface(form_page)
                    if form_surface is form_page and not (
                        form_page.locator('button[type="submit"], input[type="submit"]').count()
                        or form_page.get_by_label(re.compile(r"e-?mail", re.I)).count()
                    ):
                        fallback = greenhouse_fallback_url(job)
                        if fallback:
                            form_page.goto(fallback, wait_until="commit", timeout=20_000)
                            form_page = open_application_form(form_page, context)
                            form_surface = find_application_surface(form_page)
                    fill_standard_fields(form_surface, profile, job)
                    status, note = submit_if_safe(form_surface, allow_submit, wait_for_code)
            except Exception as error:
                print(f"[WARNING] {job['company']}: {error}")
                status = "NEEDS_REVIEW"
                note = f"Automation error: {error}"
            update_job_status(worksheet, job["row_number"], status, note)
            print(f"[INFO] {job['company']}: {status} - {note}")
        context.close()


def diagnose_jobs(jobs: list[dict]) -> None:
    """Inspect form surfaces without filling, submitting, or updating Sheets."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit("Playwright is not installed.") from error

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            ".job-radar-browser", headless=False
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(8_000)
        for job in jobs:
            print(f"[DIAG] Opening {job['company']} | {job['title']}")
            try:
                page.goto(job["apply_url"], wait_until="commit", timeout=20_000)
                form_page = open_application_form(page, context)
                print(f"[DIAG] page={form_page.url} frames={len(form_page.frames)}")
                for index, surface in enumerate([form_page, *form_page.frames]):
                    try:
                        buttons = surface.locator("button").all_inner_texts()
                        submits = surface.locator('button[type="submit"], input[type="submit"]').count()
                        required = surface.locator(
                            "input[required], textarea[required], select[required], "
                            "input[aria-required=true], textarea[aria-required=true], select[aria-required=true]"
                        ).count()
                        print(f"[DIAG] surface={index} url={surface.url} buttons={buttons[:12]} submits={submits} required={required}")
                    except Exception as error:
                        print(f"[DIAG] surface={index} unreadable: {error}")
            except Exception as error:
                print(f"[DIAG] {job['company']}: {error}")
        context.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true", help="Write the eligible job queue without opening a browser.")
    parser.add_argument("--submit", action="store_true", help="Allow submission only for fully completed, CAPTCHA-free forms.")
    parser.add_argument("--minimum-score", type=float, default=90)
    parser.add_argument("--limit", type=int, default=10, help="Maximum applications to open in one run (default: 10).")
    parser.add_argument("--retry-review", action="store_true", help="Include existing NEEDS_REVIEW jobs after updating the application profile.")
    parser.add_argument("--retry-captcha", action="store_true", help="Retry CAPTCHA-blocked jobs explicitly; normally they are skipped to reach other jobs.")
    parser.add_argument("--prune-expired", action="store_true", help="Mark closed or missing job pages EXPIRED without filling or submitting forms.")
    parser.add_argument("--diagnose", action="store_true", help="Inspect the next forms without filling, submitting, or changing Sheet statuses.")
    parser.add_argument("--wait-for-code", action="store_true", help="Pause for manual email-verification-code entry, then continue automatically.")
    args = parser.parse_args()

    config = load_yaml("config.yaml")
    worksheet = get_worksheet(config)
    jobs = queue_jobs(
        worksheet,
        args.minimum_score,
        args.retry_review or args.prune_expired,
        args.retry_captcha,
    )
    write_queue(jobs)
    if args.plan:
        return

    jobs = jobs[:max(args.limit, 0)]
    print(f"[INFO] Processing {len(jobs)} jobs in this batch")

    if args.diagnose:
        diagnose_jobs(jobs)
        return

    profile_path = Path(PROFILE_FILE)
    if not profile_path.is_file():
        raise SystemExit(f"Create {PROFILE_FILE} from application_profile.example.yaml first.")
    process_jobs(jobs, load_yaml(PROFILE_FILE), worksheet, args.submit, args.prune_expired, args.wait_for_code)


if __name__ == "__main__":
    main()
