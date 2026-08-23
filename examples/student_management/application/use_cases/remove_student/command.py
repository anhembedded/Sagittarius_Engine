from dataclasses import dataclass


@dataclass
class RemoveStudentCommand:
    student_id: str
