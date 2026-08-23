from dataclasses import dataclass


@dataclass
class UpdateStudentCommand:
    student_id: str
    full_name: str | None = None
    email: str | None = None
    major: str | None = None
    gpa: float | None = None
