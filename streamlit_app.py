"""Card-based mobile dashboard for Streamlit Community Cloud."""
import streamlit as st
import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Job Radar", page_icon="🎯", layout="centered")
st.title("🎯 Job Radar")
st.caption("Fresh opportunities matched to your profile")

def get_rows():
    cfg = st.secrets.get("google_service_account")
    workbook = st.secrets.get("workbook_name", "Job Radar")
    spreadsheet_id = st.secrets.get("spreadsheet_id")
    if not cfg:
        st.error("Add google_service_account and workbook_name in Streamlit Secrets.")
        st.stop()
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    client = gspread.authorize(Credentials.from_service_account_info(dict(cfg), scopes=scopes))
    try:
        book = client.open_by_key(spreadsheet_id) if spreadsheet_id else client.open(workbook)
    except APIError as exc:
        st.error("Google Sheets access failed. Share the spreadsheet with the service-account email and verify spreadsheet_id in Secrets.")
        st.code(str(exc))
        st.stop()
    rows = []
    for ws in book.worksheets(): rows.extend(ws.get_all_records())
    return rows

rows = get_rows()
rows = [r for r in rows if str(r.get("Status", "")).upper() not in {"EXPIRED", "APPLIED"}]
def number(value, default):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default

rows.sort(key=lambda r: (-number(r.get("Match Score", 0), 0), number(r.get("Days Old", 999), 999)))
india_terms = ("india", "pune", "mumbai", "bengaluru", "bangalore", "hyderabad")
india = [r for r in rows if any(x in str(r.get("Location", "")).lower() for x in india_terms)][:25]
remote = [r for r in rows if r not in india][:25]
apac = [r for r in remote if any(x in str(r.get("Location", "")).lower() for x in ("apac", "asia pacific", "asia-pacific"))][:25]
remote = [r for r in remote if r not in apac][:25]

def show(title, items):
    st.subheader(f"{title} ({len(items)})")
    for r in items:
        score = number(r.get("Match Score", 0), 0)
        st.markdown(f"**{r.get('Role', 'Untitled role')}**  ")
        st.caption(f"{r.get('Company', '')} · {r.get('Location', 'Location not specified')} · {score:.0f}/100 · {r.get('Days Old', '?')}d old")
        skills = r.get("Matched Skills", "")
        if skills: st.write(f"Skills: {skills}")
        if r.get("Apply Link"): st.link_button("View opportunity →", r["Apply Link"])
        st.divider()

show("🇮🇳 India opportunities", india)
show("🌍 Remote / worldwide opportunities", remote)
show("🌏 APAC opportunities (verify eligibility)", apac)
