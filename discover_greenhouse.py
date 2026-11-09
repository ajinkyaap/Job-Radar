import yaml
import requests


with open(
    "companies_master.yaml",
    "r",
    encoding="utf-8"
) as f:

    companies = yaml.safe_load(
        f
    )["companies"]


valid_boards = []


for company in companies:

    url = (
        f"https://boards-api.greenhouse.io/"
        f"v1/boards/{company}/jobs"
    )

    try:

        response = requests.get(
            url,
            timeout=10
        )

        if response.status_code == 200:

            jobs = response.json().get(
                "jobs",
                []
            )

            print(
                f"✅ {company}: "
                f"{len(jobs)} jobs"
            )

            valid_boards.append(
                company
            )

        else:

            print(
                f"❌ {company}"
            )

    except Exception:

        print(
            f"❌ {company}"
        )


with open(
    "greenhouse_verified.yaml",
    "w",
    encoding="utf-8"
) as f:

    yaml.dump(
        {
            "greenhouse":
            valid_boards
        },
        f
    )