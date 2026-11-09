import requests
import csv
from concurrent.futures import ThreadPoolExecutor


TIMEOUT = 8


ATS_CHECKS = {

    "greenhouse":
        "https://boards-api.greenhouse.io/v1/boards/{}/jobs",

    "lever":
        "https://api.lever.co/v0/postings/{}?mode=json",

    "ashby":
        "https://jobs.ashbyhq.com/{}",

    "smartrecruiters":
        "https://api.smartrecruiters.com/v1/companies/{}/postings",

    "workable":
        "https://apply.workable.com/api/v1/widget/accounts/{}",
}


with open(
    "companies_master.txt",
    "r",
    encoding="utf-8"
) as f:

    COMPANIES = [
        line.strip()
        for line in f
        if line.strip()
    ]


def check_board(
    company,
    board,
    url_template
):

    url = url_template.format(
        company
    )

    try:

        response = requests.get(
            url,
            timeout=TIMEOUT
        )

        if response.status_code == 200:

            return (
                company,
                board,
                True
            )

    except Exception:
        pass

    return (
        company,
        board,
        False
    )


results = {}

for company in COMPANIES:

    results[company] = []


tasks = []


with ThreadPoolExecutor(
    max_workers=20
) as executor:

    futures = []

    for company in COMPANIES:

        for board, url in ATS_CHECKS.items():

            futures.append(

                executor.submit(
                    check_board,
                    company,
                    board,
                    url
                )

            )

    for future in futures:

        company, board, found = (
            future.result()
        )

        if found:

            results[
                company
            ].append(
                board
            )


print("\n")

print("=" * 60)
print("DISCOVERED BOARDS")
print("=" * 60)

for company, boards in (
    results.items()
):

    if boards:

        print(
            f"{company}: "
            f"{', '.join(boards)}"
        )

with open(
    "company_to_board.csv",
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "Company",
        "Greenhouse",
        "Lever",
        "Ashby",
        "SmartRecruiters",
        "Workable"
    ])

    for company, boards in results.items():

        writer.writerow([
            company,
            "greenhouse" in boards,
            "lever" in boards,
            "ashby" in boards,
            "smartrecruiters" in boards,
            "workable" in boards,
        ])

print(
    "\nSaved to "
    "company_to_board.csv"
)