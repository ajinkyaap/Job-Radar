import smtplib
from html import escape
from pathlib import Path
import yaml

from email.mime.text import MIMEText

from email.mime.multipart \
    import MIMEMultipart


def _candidate_profile():
    path = Path("application_profile.yaml")
    if not path.is_file():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _eligibility(location, profile):
    india_terms = ("india", "pune", "mumbai", "bengaluru", "bangalore", "hyderabad")
    policy = "india" if any(term in (location or "").lower() for term in india_terms) else "other_countries"
    return (profile.get("eligibility") or {}).get(policy, {})


def create_email_html(jobs):
    """Create a concise shortlist grouped by India and remote/worldwide roles."""
    india_cards = []
    remote_cards = []
    for job in jobs:
        skills = ", ".join(job.matched_skills or []) or "Review job description"
        role_type = getattr(job, "role_type", "") or ("Remote" if job.remote else "Role")
        friction = getattr(job, "application_friction", 0)
        note = "Fresh match" if job.days_old <= 3 else "Relevant match"
        score_color = "#087f5b" if job.score >= 90 else "#b7791f" if job.score >= 80 else "#6b7280"
        age_label = "today" if job.days_old == 0 else f"{job.days_old}d ago"
        card = f"""
        <table role="presentation" width="100%" style="border-collapse:separate;border-spacing:0;margin:12px 0;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden">
          <tr><td style="padding:16px 18px 4px">
            <div style="font-size:17px;font-weight:700;color:#172554">{escape(str(job.title))}</div>
            <div style="margin-top:5px;color:#475569"><b>{escape(str(job.company))}</b> · {escape(str(job.location or "Location not specified"))} · {escape(role_type)}</div>
          </td><td align="right" valign="top" style="padding:16px 18px 4px;white-space:nowrap">
            <span style="background:{score_color};color:#fff;padding:5px 9px;border-radius:14px;font-weight:700;font-size:13px">{job.score:.0f}/100</span>
          </td></tr>
          <tr><td colspan="2" style="padding:5px 18px 14px;color:#64748b;font-size:13px">
            <b>Skills:</b> {escape(skills)} &nbsp;·&nbsp; <b>Posted:</b> {age_label} &nbsp;·&nbsp; <b>Source:</b> {escape(str(job.source))} &nbsp;·&nbsp; {note}
            {('<br><span style="color:#b45309">Application may need extra verification steps</span>' if friction else '')}
          </td></tr>
          <tr><td colspan="2" style="padding:0 18px 16px"><a href="{escape(str(job.apply_url), quote=True)}" style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;padding:9px 14px;border-radius:6px;font-weight:600;font-size:13px">View opportunity →</a></td></tr>
        </table>
        """
        india_terms = ("india", "pune", "mumbai", "bengaluru", "bangalore", "hyderabad")
        (india_cards if any(term in (job.location or "").lower() for term in india_terms) else remote_cards).append(card)
    sections = []
    if india_cards:
        sections.append("<h2 style='color:#1d4ed8;margin:24px 0 8px'>🇮🇳 India opportunities <span style='font-size:13px;color:#64748b;font-weight:normal'>({})</span></h2>".format(len(india_cards)) + "".join(india_cards))
    if remote_cards:
        sections.append("<h2 style='color:#1d4ed8;margin:24px 0 8px'>🌍 Remote / worldwide opportunities <span style='font-size:13px;color:#64748b;font-weight:normal'>({})</span></h2><p style='color:#64748b;font-size:13px'>Remote availability can still be country-restricted.</p>".format(len(remote_cards)) + "".join(remote_cards))
    return """<html><body style="margin:0;background:#eef4ff;font-family:Arial,sans-serif;color:#1e293b">
      <div style="max-width:760px;margin:0 auto;padding:28px 18px">
      <div style="background:linear-gradient(135deg,#172554,#2563eb);border-radius:14px;padding:24px;color:#fff">
        <div style="font-size:12px;letter-spacing:1.5px;text-transform:uppercase;opacity:.8">JOB RADAR</div>
        <h1 style="margin:8px 0 4px;font-size:28px">Your freshest opportunities</h1>
        <p style="margin:0;opacity:.9">Ranked by profile fit and posting freshness.</p>
      </div>
      {sections}
      <p style="font-size:12px;color:#64748b;margin-top:24px">Scores are advisory matches based on the available job description. Review the employer page for eligibility, compensation, and role details.</p>
      </div>
    </body></html>""".format(sections="".join(sections))


def send_email(
    sender,
    password,
    receiver,
    jobs
):

    if not jobs:
        return

    html = create_email_html(jobs)

    msg = MIMEMultipart()

    msg["Subject"] = f"[Job Radar] Top {len(jobs)} application-ready matches"

    msg["From"] = sender

    msg["To"] = receiver

    msg.attach(
        MIMEText(
            html,
            "html"
        )
    )

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
