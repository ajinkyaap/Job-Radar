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


valid = []


for company in companies:

    url = (
        f"https://api.lever.co/"
        f"v0/postings/"
        f"{company}"
        f"?mode=json"
    )

    try:

        r = requests.get(
            url,
            timeout=10
        )

        data = r.json()

        if isinstance(
            data,
            list
        ):

            print(
                f"✅ {company}: "
                f"{len(data)} jobs"
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
    "lever_verified.yaml",
    "w"
) as f:

    yaml.dump(
        {
            "lever":
            valid
        },
        f
    )