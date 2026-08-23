from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent

# Every event below needs `def __post_init__(self): BaseEvent.__init__(self)`.
# BaseEvent is not itself a dataclass, so @dataclass's generated __init__ never
# calls it automatically. Forgetting this line raises nothing at construction
# time — the object builds fine — and only fails later, on first access to
# `.event_id`/`.occurred_on`/`.to_dict()`, with
# `AttributeError: '<EventName>' object has no attribute '_event_id'`.
# Verified 2026-08-23. Adding a new event class here: copy the pattern below.


@dataclass
class StudentEnrolled(BaseEvent):
    student_id: str
    full_name: str

    def __post_init__(self) -> None:
        BaseEvent.__init__(self)


@dataclass
class StudentUpdated(BaseEvent):
    student_id: str
    changed_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        BaseEvent.__init__(self)


@dataclass
class StudentRemoved(BaseEvent):
    student_id: str

    def __post_init__(self) -> None:
        BaseEvent.__init__(self)
