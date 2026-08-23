from dataclasses import dataclass
from datetime import datetime


@dataclass
class ListStudentsByEnrollmentDateQuery:
    from_dt: datetime | None
    to_dt: datetime | None
