from __future__ import annotations
from typing import Literal, Optional
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from models.character import Character


@dataclass
class Task:
    id: int
    type: Literal["craft", "gather", "fight", "items"]

    target: str
    quantity_total: int
    skill: str | None = None
    skill_level: int | None = None
    parent_id: int = 0
    status: Literal["pending", "assigned", "running", "done", "cancelled"] = "pending"
    assigned_to: str | None = None
    recipe: list | None = None

    def is_ready(self, bank_content, characters):
        # 1. banque
        if bank_content.get(self.target, 0) >= self.quantity_total:
            return True

        # 2. un personnage a le niveau requis
        if self.skill:
            for char in characters.values():
                if getattr(char, f"{self.skill}_level", 0) >= self.skill_level:
                    return True

        return False

    def missing_materials(self, bank_content):
        if self.type != "craft" or not self.recipe:
            return []

        missing = []
        for ing in self.recipe:
            code = ing["code"]
            qty = ing["quantity"] * self.quantity_total
            bank_qty = bank_content.get(code, 0)

            if bank_qty < qty:
                missing.append((code, qty - bank_qty))

        return missing

    def find_eligible_character(self, characters):
        if not self.skill:
            return list(characters.values())

        attr = f"{self.skill}_level"
        eligible = [
            char
            for char in characters.values()
            if getattr(char, attr, 0) >= self.skill_level
        ]

        return sorted(eligible, key=lambda c: getattr(c, attr, 0))


@dataclass
class TaskResult:
    task_id: int
    character: "Character"
    success: bool
