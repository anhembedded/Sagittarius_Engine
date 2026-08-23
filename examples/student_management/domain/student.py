from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime


@dataclass(frozen=True)
class StudentId:
    value: str

    @classmethod
    def new(cls) -> "StudentId":
        return cls(str(uuid.uuid4()))


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        local, _, domain = self.value.partition("@")
        if not local or not domain or "." not in domain:
            raise ValueError(f"Invalid email address: {self.value!r}")


MIN_GPA = 0.0
MAX_GPA = 4.0


@dataclass
class Student:
    id: StudentId
    full_name: str
    email: Email
    major: str
    gpa: float
    enrolled_at: datetime

    def __post_init__(self) -> None:
        self._validate_gpa(self.gpa)
        if not self.full_name.strip():
            raise ValueError("full_name must not be empty")
        if not self.major.strip():
            raise ValueError("major must not be empty")

    @staticmethod
    def _validate_gpa(gpa: float) -> None:
        if not (MIN_GPA <= gpa <= MAX_GPA):
            raise ValueError(f"gpa must be between {MIN_GPA} and {MAX_GPA}, got {gpa}")

    @classmethod
    def enroll(cls, full_name: str, email: Email, major: str, gpa: float) -> "Student":
        return cls(
            id=StudentId.new(),
            full_name=full_name,
            email=email,
            major=major,
            gpa=gpa,
            enrolled_at=datetime.now(UTC),
        )

    def with_updates(
        self,
        full_name: str | None = None,
        email: Email | None = None,
        major: str | None = None,
        gpa: float | None = None,
    ) -> "Student":
        if gpa is not None:
            self._validate_gpa(gpa)
        return replace(
            self,
            full_name=full_name if full_name is not None else self.full_name,
            email=email if email is not None else self.email,
            major=major if major is not None else self.major,
            gpa=gpa if gpa is not None else self.gpa,
        )
