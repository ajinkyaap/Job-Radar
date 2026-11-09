"""Run Job Radar repeatedly for lightweight scheduled polling.

Example: python run_radar_loop.py --interval-minutes 180
Stop with Ctrl+C. Windows Task Scheduler can invoke main.py directly instead.
"""
import argparse
import time

from main import main


parser = argparse.ArgumentParser()
parser.add_argument("--interval-minutes", type=int, default=180)
args = parser.parse_args()

while True:
    main()
    print(f"[INFO] Next scan in {args.interval_minutes} minutes")
    time.sleep(max(args.interval_minutes, 15) * 60)
