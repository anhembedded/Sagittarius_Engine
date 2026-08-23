import pytest

from examples.student_management.domain.student import Email, Student, StudentId


def test_email_rejects_missing_at_sign():
    with pytest.raises(ValueError):
        Email("not-an-email")


def test_email_rejects_domain_without_dot():
    with pytest.raises(ValueError):
        Email("a@b")


def test_email_accepts_valid_address():
    assert Email("a@b.com").value == "a@b.com"


def test_student_enroll_generates_id_and_timestamp():
    s = Student.enroll("Alice", Email("a@b.com"), "CS", 3.5)
    assert isinstance(s.id, StudentId)
    assert s.enrolled_at is not None


@pytest.mark.parametrize("bad_gpa", [-0.1, 4.1, 10.0])
def test_student_rejects_out_of_range_gpa(bad_gpa):
    with pytest.raises(ValueError):
        Student.enroll("Alice", Email("a@b.com"), "CS", bad_gpa)


def test_student_rejects_blank_full_name():
    with pytest.raises(ValueError):
        Student.enroll("   ", Email("a@b.com"), "CS", 3.0)


def test_with_updates_only_changes_given_fields():
    s = Student.enroll("Alice", Email("a@b.com"), "CS", 3.5)
    updated = s.with_updates(gpa=3.9)

    assert updated.gpa == 3.9
    assert updated.full_name == s.full_name
    assert updated.email == s.email
    assert updated.id == s.id
    # original unchanged (with_updates returns a copy)
    assert s.gpa == 3.5


def test_with_updates_validates_new_gpa():
    s = Student.enroll("Alice", Email("a@b.com"), "CS", 3.5)
    with pytest.raises(ValueError):
        s.with_updates(gpa=9.0)
