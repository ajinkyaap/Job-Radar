"""Shared helpers for normalising public ATS job postings."""

from bs4 import BeautifulSoup


REMOTE_TERMS = (
    "remote",
    "remote-first",
    "work from home",
    "work remotely",
    "distributed",
    "anywhere",
)


def html_to_text(value: str | None) -> str:
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def is_remote(*parts: str | None) -> bool:
    text = " ".join(part or "" for part in parts).lower()
    return any(term in text for term in REMOTE_TERMS)


def location_text(location: object) -> str:
    """Return a readable location from common ATS location payload shapes."""
    if isinstance(location, str):
        return location
    if isinstance(location, dict):
        return ", ".join(
            str(location[key])
            for key in ("name", "city", "region", "country")
            if location.get(key)
        )
    if isinstance(location, list):
        return ", ".join(location_text(item) for item in location if item)
    return ""
