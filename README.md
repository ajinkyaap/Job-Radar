# Job Radar

Job Radar is a personal job-discovery pipeline for backend-focused software-engineering roles. It collects live vacancies from configured applicant-tracking-system (ATS) boards, ranks them against a Java/backend profile, records qualifying listings in a Google Sheet, and emails newly found matches.

## What runs

The application entry point is `main.py`:

```text
company_boards.yaml
        |
        v
Greenhouse API + Lever API + Ashby API
        |
        v
normalised Job records -> duplicate removal -> scoring/filtering
        |                                  |
        v                                  v
weekly Google Sheets tab              Gmail notification
```

Run it from the repository root:

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Runtime flow

1. `main.py` loads `config.yaml` and `company_boards.yaml`.
2. `collect_jobs()` fetches all configured Greenhouse and Ashby boards concurrently (up to 10 workers per provider), then fetches Lever boards. A provider failure is isolated so the other sources still run.
3. ATS-specific modules convert provider payloads into the shared `Job` dataclass in `models.py`. HTML job descriptions are converted to plain text, and posting age is calculated in UTC.
4. Jobs with the same company and title in one run are collapsed.
5. `matcher.calculate()` applies the resume-aligned profile in `config.yaml`: it rejects stale jobs, out-of-scope locations, internships, leadership/staff roles, unrelated titles, and roles that explicitly require substantially more experience. Remaining jobs are ranked from grouped skill evidence, title, company, experience, freshness, and location signals.
6. India and remote roles use a quality floor of 72 with target-title, experience, freshness, and eligibility gates. Skill matching uses the broader grouped model so relevant roles are not discarded merely because a description omits Java or Spring terminology. Email delivery targets 10–25 India jobs and 10–25 remote/worldwide jobs, warning when fewer qualifying jobs exist.
7. A worksheet named `YYYY_W<ISO-week>` is opened or created in the configured Google Sheet. New matches are appended with metadata and a `NEW` status.
8. If anything was inserted, an HTML email containing up to `email_top_jobs_limit` jobs is sent through Gmail SMTP.

## Role-matching model

The scoring model is intentionally targeted to Java/backend/platform roles. It recognises weighted skills including Java, Spring, Kafka, microservices, AWS, Docker, Kubernetes, SQL databases, distributed systems, REST APIs, CI/CD, and financial-services terminology.

The base score is weighted as follows:

| Signal | Weight |
| --- | ---: |
| Resume skill-group coverage | 45% |
| Target title | 15% |
| Experience text | 15% |
| Company priority | 5% |
| Freshness | 10% |
| Location | 10% |

Skills are grouped to avoid artificially inflating a role for overlapping terms such as Spring, Spring Boot, and Spring Framework. Three, four, and five-or-more distinct groups receive progressively stronger skill coverage scores, so a strong role is not required to list every resume skill. Jobs must match at least three groups to avoid the low-signal penalty. Scores are capped at 100 and assigned `HIGH` at 80+, `MEDIUM` at 65+, and `LOW` otherwise. Since the main pipeline filters at 85, persisted jobs are normally `HIGH` priority.

## Project map

| Path | Purpose |
| --- | --- |
| `main.py` | Active orchestration: fetch, score, persist, and notify. |
| `ats/greenhouse.py` | Greenhouse API client, normalisation, remote detection, concurrent fetching. |
| `ats/lever.py` | Lever API client and normalisation. |
| `ats/ashby.py` | Ashby public Posting API client. |
| `ats/common.py` | Shared HTML, location, and remote-work normalisation helpers. |
| `models.py` | Shared `Job` record definition. |
| `matcher.py` | Active resume-aligned eligibility rules, skill-group matching, and priority. |
| `scoring.py` | Earlier scoring implementation retained for reference; not used by `main.py`. |
| `sheets.py` | Google service-account authentication for Sheets. |
| `emailer.py` | Gmail SMTP HTML digest delivery. |
| `utils.py` | ISO date parsing and UTC age calculation. |
| `company_boards.yaml` | Active ATS board registry. |
| `config.yaml` | Runtime thresholds plus Google Sheets and email settings. |
| `discover_*.py`, `merge_boards.py` | Utilities for probing and assembling ATS board lists; not called by `main.py`. |
| `job_radar.py` | Older, standalone implementation; not imported by the active entry point. |

## Configuration and setup

`config.yaml` supplies the match threshold, the resume-aligned `matching` profile, workbook name, credential-file path, and mail settings. The profile is tuned for 4.5 years of Java/Spring Boot backend experience with Kafka, microservices, REST APIs, PostgreSQL, AWS/DevOps, banking, and production support. `credentials.json` must be a Google service-account key whose service-account email has access to the target spreadsheet. The configured Gmail account must permit SMTP authentication (normally via an app password).

Keep `credentials.json` and SMTP credentials out of version control. Start from `config.example.yaml`; `.gitignore` excludes the local configuration and service-account key. The current configuration file contains live-looking email credentials, so they should be rotated and moved to environment variables or a secret manager before sharing this project.

## Current implementation notes

- Greenhouse, Lever, and Ashby are enabled. The Ashby client uses its structured Posting API, so it now provides individual job listings rather than an unscorable careers page.
- Source job keys and Google Sheet keys use the same company/title/location/apply-link format, preventing duplicate inserts within a weekly worksheet.
- Update the `matching` section rather than editing code to change experience, job age, locations, titles, exclusions, company priorities, or the minimum number of matching skill groups.
- `scoring.py` and `job_radar.py` are legacy implementations. The active entry point uses `matcher.py` and the modules imported by `main.py`.
- The project includes focused matcher tests but no scheduler. It runs when `python main.py` is invoked; scheduling is the next natural operational addition.

## Dependencies

The project uses Requests, Beautiful Soup, PyYAML, gspread, and Google Auth. See `requirements.txt` for the installable dependency list.

## Board health checks

Run the read-only verifier after changing `company_boards.yaml`:

```powershell
python verify_boards.py
```

It tests every configured Greenhouse, Lever, and Ashby public endpoint concurrently and reports stale, invalid, or unavailable slugs without changing Sheets, email, or configuration.

## Local checks

```powershell
python -m unittest discover -s tests
python -m py_compile main.py matcher.py verify_boards.py ats\*.py
```

## Application assistant

The assistant supports all matched locations and common Greenhouse, Lever, and Ashby fields. It keeps a persistent browser session, so you log in once, and it safely stops for CAPTCHA or unknown required questions. Its profile has country-aware eligibility: India jobs are answered `Yes` for work authorisation and `No` for sponsorship; every other location is answered `No` and `Yes`, respectively.

For Coinbase/Greenhouse verification codes, place the Gmail OAuth client file at `gmail_client_secret.json`, then authorize it once:

```powershell
python -m pip install -r requirements.txt
python gmail_reader.py
```

This creates the local `gmail_token.json` with read-only Gmail access. The application assistant can then poll for a recent verification code with `--wait-for-code`; it does not log or retain the code.

```powershell
Copy-Item application_profile.example.yaml application_profile.yaml
# Complete application_profile.yaml once, including truthful work-authorisation answers.
python -m pip install -r requirements.txt
python -m playwright install chromium
python apply_assistant.py --plan
python apply_assistant.py --limit 10
```

The default run only prefills complete forms and updates their Sheet status to `PREFILLED`; it never submits. A later `--submit` run prioritises these prefilled forms, then processes new jobs. To allow batch submission of only CAPTCHA-free forms with every required answer completed, use:

```powershell
python apply_assistant.py --submit --minimum-score 90 --limit 10
```

Browser runs process at most 10 jobs by default; use `--limit` to change the batch size. Unknown or incomplete forms are marked `NEEDS_REVIEW`. A successful submission is marked `APPLIED` only after a confirmation message is detected.

The `Application Notes` column records the exact reason for each `NEEDS_REVIEW` status. The queue processes each unique application URL only once. After adding a missing answer to the profile, retry review items with:

```powershell
python apply_assistant.py --submit --retry-review --minimum-score 90 --limit 2
```

Closed, missing, or banner-expired listings are kept for reporting but marked `EXPIRED`, which excludes them from future application batches. Check a small batch without filling or submitting forms with:

```powershell
python apply_assistant.py --prune-expired --minimum-score 90 --limit 10
```
## Resend the application-ready shortlist

To email the current eligible jobs already stored in Google Sheets, without fetching or applying:

```powershell
python send_shortlist.py --minimum-score 90 --limit 25
```

The email deduplicates apply links, excludes `EXPIRED` and `APPLIED` rows, and sends a concise digest grouped into India-based and remote/worldwide sections with score, location, matched skills, age, and a direct application link. It intentionally omits the application checklist; eligibility and sponsorship still need to be verified on the employer form.

Remote roles are accepted only when explicitly labelled `Remote`, `Remote - India`, `Worldwide`, `Global`, `Anywhere`, or `Work from anywhere`. Country qualifiers remain excluded. APAC roles are shown in a separate lower-confidence section because APAC may include India but can also be restricted to other countries. India-based non-remote roles remain eligible.

## Continuous scanning and analytics

For periodic polling in a terminal, run `python run_radar_loop.py --interval-minutes 180`. For unattended Windows operation, schedule `python main.py` in Task Scheduler. The matcher records role type and application-friction signals for ranking and email context. To review outcomes and source performance from Google Sheets, run `python analytics_report.py`; update each row's `Status` with values such as `APPLIED`, `INTERVIEW`, `SHORTLISTED`, or `REJECTED`.

## Mobile access and daily 10:00 IST scans

`mobile_app.py` provides a phone-friendly dashboard backed by the latest Google Sheet data. Run locally with `python mobile_app.py` and open `http://localhost:5000`; for real phone access, deploy it to a private hosting service such as Render or Railway and configure `JOB_RADAR_ADMIN_TOKEN` as an environment secret. Do not commit `config.yaml` or `credentials.json`.

### Render deployment

The `render.yaml` Blueprint defines the dashboard web service and the daily cron scan. In Render, choose **New → Blueprint**, connect this repository, and select the `cloud` branch. Render will create both services. In each service's **Environment → Secret Files**, add `config.yaml`, `credentials.json`, and `application_profile.yaml`. Set `google_sheet.credentials_file` in the secret `config.yaml` to `/etc/secrets/credentials.json`. The Blueprint already sets `JOB_RADAR_CONFIG_PATH=/etc/secrets/config.yaml`; set a strong `JOB_RADAR_ADMIN_TOKEN` on the web service. Add the same secret files to the cron service. Render cron schedules use UTC, so `30 4 * * *` runs at 10:00 IST.

### No-card option: Streamlit Community Cloud

If a hosting provider requests a payment card, deploy `streamlit_app.py` on Streamlit Community Cloud instead. It provides a phone-friendly `streamlit.app` URL and supports app secrets. Select the repository, branch `cloud`, and file `streamlit_app.py`, then add `google_service_account` (the service-account JSON fields as TOML), `workbook_name = "Job Radar"`, and `spreadsheet_id = "your-sheet-id"` in the app Secrets panel. Use the ID from the Google Sheets URL and share the spreadsheet with the `client_email` from `credentials.json` as an Editor. Keep the GitHub Actions workflow for the daily 10:00 IST scan; it updates Sheets and sends email independently of the dashboard.

The included `.github/workflows/daily-radar.yml` runs every day at 10:00, 13:00, and 21:00 Asia/Kolkata (04:30, 07:30, and 15:30 UTC) and can also be started manually. In repository secrets, add `JOB_RADAR_CONFIG_B64` and `JOB_RADAR_CREDENTIALS_B64`, containing base64-encoded versions of the local `config.yaml` and `credentials.json`. The workflow then installs dependencies, runs `main.py`, updates Sheets, and sends the digest email.

The `ATS Board Health` workflow checks every configured Greenhouse, Lever, Ashby, and SmartRecruiters endpoint weekly and can be started manually. Review its output before retaining newly discovered boards.

Workday support uses each employer's public CXS jobs endpoint. Add only verified entries to `company_boards.yaml` under `workday`, using the structure in `workday_boards.example.yaml`, then run `python verify_boards.py`. Workday tenant/site identifiers differ per employer, so the connector intentionally starts empty rather than guessing URLs.

Google discovery is an optional supplement, not a replacement for ATS feeds. Configure `google_search` in `config.yaml` and set `GOOGLE_SEARCH_API_KEY` plus `GOOGLE_SEARCH_CX` as runtime secrets. It uses Google's Programmable Search JSON API, filters to career/job URLs, fetches the public page, and sends candidates through the same matcher. Without those secrets it safely skips discovery.

Shortlists are grouped into India-based roles and remote/worldwide roles. Remote roles receive the same location score as India roles; work authorisation and sponsorship are shown separately because a remote label does not guarantee eligibility in the candidate's country.
# Expanding the company registry

The repository includes a generated expansion registry with 500 additional
public Greenhouse, Lever, and Ashby boards. Refresh it with:

```powershell
python expand_company_registry.py --target 500
```

The source is the LastRound AI ATS Company Directory (CC BY 4.0). Boards are
still treated as best-effort: companies can change ATS providers or close their
boards, and each connector isolates failures so one dead board cannot stop a
scheduled run. Job Radar's matcher filters the expanded feed to software-
engineering roles and the configured India/APAC/worldwide-remote criteria.

