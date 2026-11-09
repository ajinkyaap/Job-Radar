import gspread

from google.oauth2.service_account \
    import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def get_client(
    credential_file
):

    creds = (
        Credentials
        .from_service_account_file(
            credential_file,
            scopes=SCOPES
        )
    )

    return gspread.authorize(
        creds
    )