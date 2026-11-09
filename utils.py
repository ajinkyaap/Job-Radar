from datetime import datetime
from datetime import timezone
from datetime import UTC


def now_utc():

    return datetime.now(
        timezone.utc
    )


def parse_date(value):

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value /= 1000
        return datetime.fromtimestamp(value, tz=UTC)

    if not isinstance(value, str) or not value.strip():
        return None

    try:

        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )

    except:

        return None





def calculate_days_old(dt):

    if not dt:
        return 999

    if isinstance(dt, str):
        dt = parse_date(dt)
        if not dt:
            return 999

    if dt.tzinfo is None:

        dt = dt.replace(
            tzinfo=UTC
        )

    return max((now_utc() - dt).days, 0)
