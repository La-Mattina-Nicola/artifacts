from __future__ import annotations
from typing import Literal
from dataclasses import dataclass

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from models.character import Character


@dataclass
class Task:
    id: int
    root_request_id: int
    parent_id: int | None
    type: Literal["craft", "gather", "fight", "level_up"]
    target: str
    priority: int
    required_skill: str | None
    required_skill_level: int
    required_materials: list
    status: Literal["pending", "assigned", "running", "done", "cancelled"]
    assigned_to: str | None
    quantity: int = 1

    def is_ready(self, bank_content, characters):
        # Vérifie si toutes les conditions sont remplies pour assigner la tâche — skill OK + matériaux OK
        pass

    def missing_materials(self, bank_content: dict) -> list:
        missings = []
        for mat in self.required_materials:
            need = mat["quantity"] * self.quantity
            dispo = bank_content.get(mat["code"], 0)
            if dispo < need:
                missings.append({"code": mat["code"], "quantity": need - dispo})
        return missings

    def find_eligible_character(self, characters: dict) -> "Character | None":
        for char in characters.values():
            if self.required_skill is None:
                return char
            skill_level = getattr(char, f"{self.required_skill}_level", 0)
            if skill_level >= self.required_skill_level:
                return char
        return None

    def cancel(self):
        self.status = "cancelled"

    def mark_done(self):
        self.status = "done"


@dataclass
class TaskResult:
    task_id: int
    character: "Character"
    success: bool
