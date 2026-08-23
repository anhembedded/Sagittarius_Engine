from dataclasses import dataclass


@dataclass
class EnrollStudentCommand:
    full_name: str
    email: str
    major: str
    gpa: float
