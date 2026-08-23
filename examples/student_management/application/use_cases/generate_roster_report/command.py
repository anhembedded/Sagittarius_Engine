from dataclasses import dataclass, field


@dataclass
class GenerateRosterReportQuery:
    pass


@dataclass
class RosterReport:
    total_students: int
    average_gpa: float
    students_by_major: dict[str, int] = field(default_factory=dict)
