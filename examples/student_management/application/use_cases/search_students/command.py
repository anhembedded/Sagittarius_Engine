from dataclasses import dataclass


@dataclass
class SearchStudentsQuery:
    name_contains: str
