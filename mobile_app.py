"""Mobile-friendly dashboard. Run with: python mobile_app.py"""
import os
from datetime import UTC, datetime
from flask import Flask, abort, redirect, render_template_string, request
from main import get_or_create_sheet, main

app = Flask(__name__)
PAGE = """<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Job Radar</title><style>body{font-family:system-ui;background:#eef4ff;margin:0;color:#172554}.wrap{max-width:760px;margin:auto;padding:18px}.head{background:linear-gradient(135deg,#172554,#2563eb);color:white;padding:22px;border-radius:16px}.card{background:white;border-radius:12px;padding:16px;margin:10px 0;box-shadow:0 2px 8px #dbe4f0}.score{float:right;background:#087f5b;color:white;padding:5px 9px;border-radius:15px;font-weight:bold}a{color:#2563eb;font-weight:600}small{color:#64748b}</style><div class=wrap><div class=head><h1>Job Radar</h1><div>Fresh opportunities matched to your profile</div><small style='color:#dbeafe'>Updated {{ updated }}</small></div>{% for section,jobs in sections %}<h2>{{ section }}</h2>{% for j in jobs %}<div class=card><span class=score>{{ '%.0f'|format(j.score) }}/100</span><b>{{ j.title }}</b><br>{{ j.company }} · {{ j.location or 'Location not specified' }}<br><small>{{ j.days_old }}d old · {{ j.source }} · {{ ', '.join(j.matched_skills or []) }}</small><p><a href='{{ j.apply_url }}' target=_blank>View opportunity →</a></p></div>{% endfor %}{% endfor %}<form method=post action=/scan><input name=token type=password placeholder='Admin token (if enabled)'> <button>Run fresh scan</button></form></div>"""

@app.get("/")
def index():
    sheet = get_or_create_sheet()
    rows = sheet.get_all_records()[-1000:]
    from models import Job
    jobs = []
    for r in rows:
        if str(r.get("Status", "")).upper() in {"EXPIRED", "APPLIED"}: continue
        try:
            jobs.append(Job(str(r.get("Company", "")), str(r.get("Role", "")), str(r.get("Location", "")), "", str(r.get("Apply Link", "")), None, int(float(r.get("Days Old", 0) or 0)), str(r.get("Remote", "")).upper()=="YES", str(r.get("Source", "")), float(r.get("Match Score", 0) or 0), [x for x in str(r.get("Matched Skills", "")).split(",") if x]))
        except (TypeError, ValueError): pass
    jobs.sort(key=lambda j: (-j.score, j.days_old))
    india_terms = ("india", "pune", "mumbai", "bengaluru", "bangalore", "hyderabad")
    india = [j for j in jobs if any(x in j.location.lower() for x in india_terms)][:25]
    remote = [j for j in jobs if j not in india][:25]
    return render_template_string(PAGE, sections=[("India opportunities", india), ("Remote / worldwide opportunities", remote)], updated=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))

@app.post("/scan")
def scan():
    expected = os.getenv("JOB_RADAR_ADMIN_TOKEN")
    if expected and request.form.get("token") != expected: abort(403)
    main()
    return redirect("/")

if __name__ == "__main__": app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
