"""Print outcome and source analytics from the current Google Sheet."""
from collections import Counter
from config_loader import load_yaml
from sheets import get_client

config = load_yaml("config.yaml")
client = get_client(config["google_sheet"]["credentials_file"])
book = client.open(config["google_sheet"]["workbook_name"])
rows = []
for ws in book.worksheets():
    rows.extend(ws.get_all_records())
print(f"Rows analysed: {len(rows)}")
print("Status:", dict(Counter(str(r.get("Status", "UNKNOWN")) for r in rows)))
print("Sources:", dict(Counter(str(r.get("Source", "UNKNOWN")) for r in rows)))
for status in ("INTERVIEW", "SHORTLISTED", "REJECTED", "APPLIED"):
    matches = [r for r in rows if str(r.get("Status", "")).upper() == status]
    if matches:
        print(f"{status} top companies:", Counter(str(r.get("Company", "")) for r in matches).most_common(5))
