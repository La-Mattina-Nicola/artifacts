from __future__ import annotations
from typing import Literal, Optional
from dataclasses import dataclass, field

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from models.character import Character


@dataclass
class Task:
    id: int
    root_request_id: int
    parent_id: int | None
    type: Literal[
        "craft", "gather", "fight", "level_up", "deposit", "withdraw", "complete_task"
    ]
    target: str
    priority: int
    required_skill: str | None
    required_skill_level: int
    required_materials: list
    status: Literal["pending", "assigned", "running", "done", "cancelled"]
    assigned_to: str | None
    quantity: int = 1
    parent_request_id: Optional[int] = None
    quantity_completed: int = 0

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
class PendingRequest:
    """Tracks a pending request for items across multiple requesters."""

    id: int
    target: str
    quantity: int
    requester: str  # Initial requester
    requesters: list[str] = field(default_factory=list)  # All requesters
    source: tuple[str, Optional[str]] = field(
        default_factory=lambda: ("gather", None)
    )  # (type, skill)
    status: Literal["pending", "in_progress", "gathering", "completed", "blocked"] = (
        "pending"
    )
    assigned_workers: list[str] = field(default_factory=list)
    materials_pending: dict[str, int] = field(
        default_factory=dict
    )  # For craft: {material_code: needed_qty}
    pending_deposits_counter: int = 0


@dataclass
class TaskResult:
    task_id: int
    character: "Character"
    success: bool
