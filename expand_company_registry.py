"""Build a large, validated ATS registry from the public LastRound AI directory.

The source maps public Greenhouse, Lever and Ashby board slugs to companies.
This command keeps a bounded registry so scheduled scans remain predictable:

    python expand_company_registry.py --target 500

The downloaded directory is CC BY 4.0; attribution is retained in the output.
"""
import argparse
import csv
import io
from collections import defaultdict
from pathlib import Path

import requests
import yaml

SOURCE_URL = "https://raw.githubusercontent.com/fyrosofttech/lastroundai-hiring-data/main/ats-directory/lastroundai-ats-company-directory-2026-08.csv"
OUTPUT = Path("company_boards_expanded.yaml")


def build_registry(target=500, timeout=60):
    rows = csv.DictReader(io.StringIO(requests.get(SOURCE_URL, timeout=timeout).text))
    by_vendor = defaultdict(list)
    for row in rows:
        vendor = row.get("ats_vendor", "").strip().lower()
        slug = row.get("board_slug", "").strip()
        name = row.get("company_name", "").strip() or slug
        if vendor in {"greenhouse", "lever", "ashby"} and slug:
            by_vendor[vendor].append({"company": name, "slug": slug})

    # Keep coverage balanced across providers: 50% Greenhouse, 25% Lever,
    # 25% Ashby. Existing configured boards are merged and de-duplicated later.
    quotas = {
        "greenhouse": max(1, round(target * 0.50)),
        "lever": max(1, round(target * 0.25)),
        "ashby": max(1, target - round(target * 0.50) - round(target * 0.25)),
    }
    result = {vendor: values[:quotas[vendor]] for vendor, values in by_vendor.items()}
    OUTPUT.write_text(
        "# Generated from LastRound AI ATS Company Directory (CC BY 4.0).\n"
        "# Regenerate with: python expand_company_registry.py --target 500\n"
        + yaml.safe_dump(result, sort_keys=False),
        encoding="utf-8",
    )
    return sum(len(items) for items in result.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=500)
    args = parser.parse_args()
    print(f"Generated {build_registry(max(1, args.target))} ATS company boards in {OUTPUT}")
