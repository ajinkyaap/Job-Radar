"""Allow scheduled scans only during approved Asia/Kolkata windows."""
from datetime import datetime
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo("Asia/Kolkata"))
minutes = now.hour * 60 + now.minute
windows = (10 * 60, 13 * 60, 21 * 60, 21 * 60 + 15)
allowed = any(abs(minutes - window) <= 10 for window in windows)
print(f"[INFO] India time: {now:%Y-%m-%d %H:%M:%S %Z}; approved window: {allowed}")
if not allowed:
    raise SystemExit(0)
