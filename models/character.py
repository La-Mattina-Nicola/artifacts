from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from models.actions import MoveAction, FightAction, RestAction, BankAction, GatherAction
import asyncio


class BankManager:
    def __init__(self, client):
        self.client = client
        self.content: Dict[str, int] = {}
        self.gold: int = 0

    async def sync(self):
        """Synchronise tout le contenu de la banque (Items + Gold)."""
        all_items = {}
        page = 1
        while True:
            res = await self.client.get(
                "/my/bank/items", params={"page": page, "size": 100}
            )
            if res.status_code != 200:
                break
            data = res.json()
            for item in data.get("data", []):
                all_items[item["code"]] = item["quantity"]
            if page >= data.get("pages", 1):
                break
            page += 1
        self.content = all_items

        res_gold = await self.client.get("/my/bank/gold")
        if res_gold.status_code == 200:
            self.gold = res_gold.json()["data"]["quantity"]

        print(f"🏦 Banque synchronisée : {len(self.content)} types d'items.")

    async def _execute_deposit(self, char, items: list):
        """Logique interne de dépôt."""
        res = await self.client.post(
            f"/my/{char.name}/action/bank/deposit/item", json=items
        )
        if res.status_code == 200:
            for item in items:
                self.content[item["code"]] = (
                    self.content.get(item["code"], 0) + item["quantity"]
                )
            self._update_char(char, res.json()["data"])
            return True
        return False

    async def _execute_withdraw(self, char, items: list):
        """Logique interne de retrait."""
        res = await self.client.post(
            f"/my/{char.name}/action/bank/withdraw/item", json=items
        )
        if res.status_code == 200:
            for item in items:
                code, qty = item["code"], item["quantity"]
                if code in self.content:
                    self.content[code] -= qty
            self._update_char(char, res.json()["data"])
            return True
        return False

    def _update_char(self, char, data):
        """Met à jour l'état du personnage après une action."""
        char.inventory = data["character"]["inventory"]
        char.gold = data["character"]["gold"]
        char.client.cooldown_expiration = data["cooldown_expiration"]


class CharacterBankInterface:
    def __init__(self, char, shared_manager: BankManager):
        self.char = char
        self.manager = shared_manager

    async def deposit(self, items: list):
        """Dépose des items pour ce personnage spécifique."""
        return await self.manager._execute_deposit(self.char, items)

    async def withdraw(self, items: list):
        """Retire des items pour ce personnage spécifique."""
        return await self.manager._execute_withdraw(self.char, items)

    @property
    def content(self):
        """Accès direct au stock global de la banque."""
        return self.manager.content

    @property
    def gold(self):
        """Accès direct à l'or global de la banque."""
        return self.manager.gold


@dataclass
class Character:
    name: str
    level: int = 1
    hp: int = 0
    max_hp: int = 0
    x: int = 0
    y: int = 0
    gold: int = 0
    inventory_max_items: int = 20
    inventory: List[Dict[str, Any]] = field(default_factory=list)

    client: Any = field(default=None, repr=False)
    world_map: Any = field(default=None, repr=False)
    shared_bank_manager: Any = field(default=None, repr=False)

    def __post_init__(self):
        """
        S'exécute après le __init__. On attache les modules.
        """
        from models.bank import (
            CharacterBankInterface,
        )

        self.banker = CharacterBankInterface(self, self.shared_bank_manager)

        self.cooldown: int = 0
        self.skills: Dict[str, int] = {}

        self.mover = MoveAction(self)
        self.fighter = FightAction(self)
        self.rest_manager = RestAction(self)
        self.gatherer = GatherAction(self)

    async def move(self, x: int, y: int):
        return await self.mover.to_coords(x, y)

    async def attack(self):
        return await self.fighter.attack()

    async def rest(self):
        return await self.rest_manager.rest()

    async def gather(self):
        return await self.gatherer.collect()

    def inventory_is_full(self, margin: int = 5) -> bool:
        used = sum(
            item.get("quantity", 0) for item in self.inventory if item.get("code")
        )
        return (used + margin) >= self.inventory_max_items

    async def sync(self):
        """Récupère les données fraîches de l'API et hydrate la dataclass."""
        response = await self.client.get(f"/characters/{self.name}")
        if response.status_code == 200:
            data = response.json()["data"]

            self.x = data.get("x", self.x)
            self.y = data.get("y", self.y)
            self.hp = data.get("hp", self.hp)
            self.max_hp = data.get("max_hp", self.max_hp)
            self.level = data.get("level", self.level)
            self.gold = data.get("gold", self.gold)
            self.inventory = data.get("inventory", [])
            self.inventory_max_items = data.get("inventory_max_items", 20)

            self.client.cooldown_expiration = data.get("cooldown_expiration")

            print(
                f"🔄 {self.name} synchronisé (HP: {self.hp}/{self.max_hp} | Gold: {self.gold} | Pos: {self.x},{self.y})"
            )
            return True
        return False
