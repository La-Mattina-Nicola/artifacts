"""
Modèles de données ArtifactsMMO.

Toutes les classes sont des dataclasses immutables (frozen=False pour
permettre la mise à jour depuis l'API) avec des méthodes ``from_dict``
pour l'hydratation depuis les réponses JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Item ──────────────────────────────────────────────────────────────────────


@dataclass
class Item:
    """Représente un item avec son code et sa quantité."""

    code: str
    quantity: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Item":
        return cls(
            code=data["code"],
            quantity=data.get("quantity", 1),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "quantity": self.quantity}

    def __repr__(self) -> str:
        return f"Item({self.code!r} ×{self.quantity})"


# ── Inventory ─────────────────────────────────────────────────────────────────


@dataclass
class Inventory:
    """
    Inventaire d'un personnage.

    ``items`` : liste des items présents (slots non vides uniquement)
    ``max_items`` : capacité totale de l'inventaire
    """

    items: list[Item] = field(default_factory=list)
    max_items: int = 100

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Inventory":
        """
        Hydrate depuis le champ ``inventory`` d'une réponse Character.

        L'API retourne une liste de slots dont certains peuvent être vides
        (code == "" ou quantity == 0) – on les filtre.
        """
        raw_slots: list[dict] = data.get("inventory", [])
        items = [
            Item.from_dict(slot)
            for slot in raw_slots
            if slot.get("code") and slot.get("quantity", 0) > 0
        ]
        return cls(
            items=items,
            max_items=data.get("inventory_max_items", 100),
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def is_full(self) -> bool:
        """True si tous les slots sont occupés."""
        return len(self.items) >= self.max_items

    @property
    def used_slots(self) -> int:
        return len(self.items)

    @property
    def free_slots(self) -> int:
        return max(0, self.max_items - self.used_slots)

    def count(self, item_code: str) -> int:
        """Quantité totale d'un item donné dans l'inventaire."""
        return sum(i.quantity for i in self.items if i.code == item_code)

    def has(self, item_code: str, quantity: int = 1) -> bool:
        return self.count(item_code) >= quantity

    def __repr__(self) -> str:
        return f"Inventory({self.used_slots}/{self.max_items} slots, {len(self.items)} types)"


# ── Bank ──────────────────────────────────────────────────────────────────────


@dataclass
class Bank:
    """
    Banque du compte (partagée entre tous les personnages).

    ``items`` : items stockés en banque
    ``gold``  : or disponible en banque
    ``slots`` : nombre de slots actuellement disponibles
    ``expansions`` : nombre d'extensions achetées
    """

    gold: int = 0
    items: list[Item] = field(default_factory=list)
    slots: int = 0
    expansions: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Bank":
        """Hydrate depuis la réponse de GET /my/bank."""
        return cls(
            gold=data.get("gold", 0),
            slots=data.get("slots", 0),
            expansions=data.get("expansions", 0),
            items=[],  # Les items sont chargés séparément via /my/bank/items
        )

    def update_items(self, raw_items: list[dict[str, Any]]) -> None:
        """Met à jour la liste d'items depuis /my/bank/items."""
        self.items = [Item.from_dict(i) for i in raw_items if i.get("code")]

    def count(self, item_code: str) -> int:
        return sum(i.quantity for i in self.items if i.code == item_code)

    def has(self, item_code: str, quantity: int = 1) -> bool:
        return self.count(item_code) >= quantity

    def __repr__(self) -> str:
        return f"Bank(gold={self.gold}, items={len(self.items)}, slots={self.slots})"


# ── Skill ─────────────────────────────────────────────────────────────────────


@dataclass
class Skill:
    """Niveau et XP d'un skill."""

    level: int = 1
    xp: int = 0
    max_xp: int = 150  # XP nécessaire pour le niveau suivant

    @property
    def xp_percent(self) -> float:
        if self.max_xp == 0:
            return 0.0
        return round(self.xp / self.max_xp * 100, 1)

    def __repr__(self) -> str:
        return (
            f"Skill(lv={self.level}, xp={self.xp}/{self.max_xp} [{self.xp_percent}%])"
        )


@dataclass
class Skills:
    """Ensemble des skills d'un personnage."""

    mining: Skill = field(default_factory=Skill)
    woodcutting: Skill = field(default_factory=Skill)
    fishing: Skill = field(default_factory=Skill)
    weaponcrafting: Skill = field(default_factory=Skill)
    gearcrafting: Skill = field(default_factory=Skill)
    jewelrycrafting: Skill = field(default_factory=Skill)
    cooking: Skill = field(default_factory=Skill)
    alchemy: Skill = field(default_factory=Skill)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skills":
        """
        Hydrate depuis le dictionnaire du personnage.

        L'API utilise le pattern : ``{skill}_level`` et ``{skill}_xp``
        et ``{skill}_max_xp``.
        """

        def _skill(name: str) -> Skill:
            return Skill(
                level=data.get(f"{name}_level", 1),
                xp=data.get(f"{name}_xp", 0),
                max_xp=data.get(f"{name}_max_xp", 150),
            )

        return cls(
            mining=_skill("mining"),
            woodcutting=_skill("woodcutting"),
            fishing=_skill("fishing"),
            weaponcrafting=_skill("weaponcrafting"),
            gearcrafting=_skill("gearcrafting"),
            jewelrycrafting=_skill("jewelrycrafting"),
            cooking=_skill("cooking"),
            alchemy=_skill("alchemy"),
        )


# ── Equipment ─────────────────────────────────────────────────────────────────

# Slots valides selon l'OpenAPI (EquipSchema)
VALID_SLOTS = frozenset(
    {
        "weapon",
        "shield",
        "helmet",
        "body_armor",
        "leg_armor",
        "boots",
        "ring1",
        "ring2",
        "amulet",
        "artifact1",
        "artifact2",
        "artifact3",
        "utility1",
        "utility2",
        "rune",
    }
)


@dataclass
class Equipment:
    """Équipement actuellement porté par le personnage."""

    weapon: str = ""
    shield: str = ""
    helmet: str = ""
    body_armor: str = ""
    leg_armor: str = ""
    boots: str = ""
    ring1: str = ""
    ring2: str = ""
    amulet: str = ""
    artifact1: str = ""
    artifact2: str = ""
    artifact3: str = ""
    utility1: str = ""
    utility2: str = ""
    rune: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Equipment":
        """
        Hydrate depuis le dictionnaire du personnage.
        L'API utilise le pattern : ``{slot}_slot`` pour chaque slot.
        """
        return cls(
            weapon=data.get("weapon_slot", ""),
            shield=data.get("shield_slot", ""),
            helmet=data.get("helmet_slot", ""),
            body_armor=data.get("body_armor_slot", ""),
            leg_armor=data.get("leg_armor_slot", ""),
            boots=data.get("boots_slot", ""),
            ring1=data.get("ring1_slot", ""),
            ring2=data.get("ring2_slot", ""),
            amulet=data.get("amulet_slot", ""),
            artifact1=data.get("artifact1_slot", ""),
            artifact2=data.get("artifact2_slot", ""),
            artifact3=data.get("artifact3_slot", ""),
            utility1=data.get("utility1_slot", ""),
            utility2=data.get("utility2_slot", ""),
            rune=data.get("rune_slot", ""),
        )

    def get_slot(self, slot: str) -> str:
        """Retourne le code de l'item équipé dans un slot donné."""
        return getattr(self, slot, "")

    def is_slot_empty(self, slot: str) -> bool:
        return not self.get_slot(slot)

    def to_dict(self) -> dict[str, str]:
        return {
            slot: getattr(self, slot) for slot in VALID_SLOTS if getattr(self, slot, "")
        }

    def __repr__(self) -> str:
        equipped = {k: v for k, v in self.to_dict().items() if v}
        return f"Equipment({equipped})"
