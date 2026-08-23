from dataclasses import dataclass


@dataclass
class GetStudentQuery:
    student_id: str
