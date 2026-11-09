import requests
import yaml


with open(
    "companies_master.yaml",
    "r"
) as f:

    companies = yaml.safe_load(
        f
    )["companies"]


valid = []


for company in companies:

    url = (
        f"https://jobs.ashbyhq.com/"
        f"{company}"
    )

    try:

        r = requests.get(
            url,
            timeout=10
        )

        if r.status_code == 200:

            print(
                f"✅ {company}"
            )

            valid.append(
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
    "ashby_verified.yaml",
    "w"
) as f:

    yaml.dump(
        {
            "ashby":
            valid
        },
        f
    )