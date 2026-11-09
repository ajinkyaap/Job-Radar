from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:

    company: str

    title: str

    location: str

    description: str

    apply_url: str

    posted_at: datetime | None

    days_old: int

    remote: bool

    source: str

    score: float = 0

    matched_skills: list[str] = field(default_factory=list)

    priority: str = ""

    domain_score: int = 0
