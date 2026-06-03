# app/models.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Employee:
    name: str
    department: str
    team_lead: str
    gender: str
    birthday: str          # "DD.MM" (may also arrive numeric from xlsx)
    country: str
    dept_chat_id: str      # column G
    extra_groups: str      # column H (comma-separated)

    def extra_group_ids(self) -> list[str]:
        if not self.extra_groups:
            return []
        return [p.strip() for p in str(self.extra_groups).split(",") if p.strip()]


@dataclass(frozen=True)
class Message:
    chat_id: int
    text: str
