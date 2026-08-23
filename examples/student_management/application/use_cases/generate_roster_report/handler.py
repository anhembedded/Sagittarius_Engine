from collections import Counter

from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.application.use_cases.generate_roster_report.command import (
    GenerateRosterReportQuery,
    RosterReport,
)


class GenerateRosterReportHandler:
    def __init__(self, repo: IStudentRepository) -> None:
        self._repo = repo

    def execute(self, dto: GenerateRosterReportQuery) -> RosterReport:
        students = self._repo.list_all()
        if not students:
            return RosterReport(total_students=0, average_gpa=0.0, students_by_major={})

        average_gpa = sum(s.gpa for s in students) / len(students)
        by_major = dict(Counter(s.major for s in students))
        return RosterReport(
            total_students=len(students),
            average_gpa=round(average_gpa, 3),
            students_by_major=by_major,
        )
