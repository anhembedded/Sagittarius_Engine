from datetime import datetime

from sqlalchemy import Float, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class StudentRecord(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    major: Mapped[str] = mapped_column(String, nullable=False)
    gpa: Mapped[float] = mapped_column(Float, nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(nullable=False)
