from __future__ import annotations
from typing import Literal
from dataclasses import dataclass

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from models.character import Character


@dataclass
class Task:
    id: isinstance
    type: Literal["craft", "gather", "fight"]
    skill: str | None
    skill_level: int | None
    target: str  # code de la ressource ou du monstre
    status: Literal["pending", "assigned", "running", "done", "cancelled"]
    assigned_to: str | None
    quantity: int = 1
    parent_id: int = 0

    def is_ready(self, bank_content, characters):
        pass

    def missing_materials(self, bank_content: dict) -> list:
        pass

    def find_eligible_character(
        self, characters: dict, skill: str, skill_level: int
    ) -> "list[Character] | None":
        attr = f"{skill}_level"
        eligible = [
            char
            for char in characters.values()
            if getattr(char, attr, 0) >= skill_level
        ]
        eligible_sorted = sorted(eligible, key=lambda c: getattr(c, attr, 0))

        return eligible_sorted


@dataclass
class TaskResult:
    task_id: int
    character: "Character"
    success: bool
