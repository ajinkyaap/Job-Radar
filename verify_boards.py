"""Read-only health check for every configured public ATS board.

Run `python verify_boards.py` before adding newly discovered slugs to
`company_boards.yaml`. It does not modify configuration or contact Sheets/email.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from config_loader import load_yaml


URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{board}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{board}/postings?limit=1",
}


def check(provider: str, board: str) -> tuple[str, str, int | None, str]:
    try:
        response = requests.get(URLS[provider].format(board=board), timeout=15)
        detail = "ok" if response.ok else response.reason
        return provider, board, response.status_code, detail
    except requests.RequestException as error:
        return provider, board, None, str(error)


def check_workday(board: dict) -> tuple[str, str, int | None, str]:
    import requests
    name = board.get("company", "unknown")
    url = f"https://{board['host']}/wday/cxs/{board['tenant']}/{board['site']}/jobs"
    try:
        response = requests.post(url, json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}, timeout=15)
        return "workday", name, response.status_code, "ok" if response.ok else response.reason
    except requests.RequestException as error:
        return "workday", name, None, str(error)


def main() -> None:
    boards = load_yaml("company_boards.yaml")
    requests_to_check = [
        (provider, board)
        for provider in URLS
        for board in boards.get(provider, [])
    ]
    workday_boards = boards.get("workday", [])
    healthy = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check, provider, board) for provider, board in requests_to_check]
        futures += [executor.submit(check_workday, board) for board in workday_boards]
        for future in as_completed(futures):
            provider, board, status, detail = future.result()
            if status == 200:
                healthy += 1
                print(f"[OK] {provider}/{board}")
            else:
                print(f"[FAIL] {provider}/{board}: {status or 'network error'} ({detail})")
    print(f"\nHealthy boards: {healthy}/{len(requests_to_check)}")


if __name__ == "__main__":
    main()
