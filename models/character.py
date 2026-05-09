import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from models.account import Account


class CharacterBankInterface:
    """Interface personnelle pour interagir avec le BankManager partagé."""

    def __init__(self, char: "Character", shared_manager):
        self.char = char
        self.manager = shared_manager

    async def deposit(self, items: list):
        return await self.manager._execute_deposit(self.char, items)

    async def withdraw(self, items: list):
        return await self.manager._execute_withdraw(self.char, items)

    @property
    def content(self):
        return self.manager.content


@dataclass
class Character:
    name: str
    account: "Account"
    level: int = 1
    hp: int = 0
    max_hp: int = 0
    x: int = 0
    y: int = 0
    gold: int = 0
    inventory_max_items: int = 20
    skin: str = "men1"
    xp: int = 0
    max_xp: int = 0
    inventory: List[Dict[str, Any]] = field(default_factory=list, repr=False)
    cooldown_expiration: str = None
    max_dmg_seen = 0

    def __post_init__(self):
        from api.client import AsyncApiClient
        from models.actions import (
            MoveAction,
            FightAction,
            RestAction,
            GatherAction,
            CraftAction,
        )

        self.client = AsyncApiClient(token=self.account.token, character=self)
        self.world_map = self.account.world
        self.items_db = self.account.items_db
        self.banker = CharacterBankInterface(self, self.account.bank)
        self.task_queue = asyncio.Queue()
        self.mover = MoveAction(self)
        self.fighter = FightAction(self)
        self.rester = RestAction(self)
        self.gatherer = GatherAction(self)
        self.crafter = CraftAction(self)

        self.default_task = None

    @property
    def is_working(self) -> bool:
        """Calcule si le personnage est occupé en temps réel."""
        if not self.cooldown_expiration:
            return False
        expire_at = datetime.fromisoformat(
            self.cooldown_expiration.replace("Z", "+00:00")
        )
        return datetime.now(timezone.utc) < expire_at

    async def wait_until_ready(self):
        """Attend le temps nécessaire sans spammer de logs."""
        if self.is_working:
            expire_at = datetime.fromisoformat(
                self.cooldown_expiration.replace("Z", "+00:00")
            )
            wait_time = (expire_at - datetime.now(timezone.utc)).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time + 1)

    async def main_loop(self):
        while True:
            try:
                await self.wait_until_ready()

                if not self.task_queue.empty():
                    task_coro = await self.task_queue.get()
                    await task_coro
                    self.task_queue.task_done()
                elif self.default_task:
                    await self.default_task()
                else:
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"⚠️ Erreur {self.name}: {e}")
                await asyncio.sleep(2)

    def update_from_api(self, data: dict):
        """Mets à jour le character à partir des données API."""
        # Champs directs simples
        self.skin = data.get("skin", self.skin)
        self.x = data.get("x", self.x)
        self.y = data.get("y", self.y)
        self.hp = data.get("hp", self.hp)
        self.max_hp = data.get("max_hp", self.max_hp)
        self.level = data.get("level", self.level)
        self.gold = data.get("gold", self.gold)
        self.inventory = data.get("inventory", self.inventory)
        self.inventory_max_items = data.get(
            "inventory_max_items", self.inventory_max_items
        )
        self.cooldown_expiration = data.get(
            "cooldown_expiration", self.cooldown_expiration
        )

        # Mettre à jour les skills dynamiquement (comme dans sync)
        for skill in [
            "mining",
            "woodcutting",
            "fishing",
            "weaponcrafting",
            "gearcrafting",
            "jewelrycrafting",
            "cooking",
            "alchemy",
        ]:
            setattr(
                self,
                f"{skill}_level",
                data.get(f"{skill}_level", getattr(self, f"{skill}_level", 1)),
            )
            setattr(
                self,
                f"{skill}_xp",
                data.get(f"{skill}_xp", getattr(self, f"{skill}_xp", 0)),
            )
            setattr(
                self,
                f"{skill}_max_xp",
                data.get(f"{skill}_max_xp", getattr(self, f"{skill}_max_xp", 150)),
            )

    async def sync(self):
        response = await self.client.get(f"/characters/{self.name}")
        if response.status_code == 200:
            data = response.json()["data"]

            self.x, self.y = data["x"], data["y"]
            self.hp, self.max_hp = data["hp"], data["max_hp"]
            self.level, self.gold = data["level"], data["gold"]
            self.inventory = data["inventory"]
            self.inventory_max_items = data["inventory_max_items"]
            self.cooldown_expiration = data["cooldown_expiration"]

            # Dans sync(), après self.inventory_max_items = ...
            for skill in [
                "mining",
                "woodcutting",
                "fishing",
                "weaponcrafting",
                "gearcrafting",
                "jewelrycrafting",
                "cooking",
                "alchemy",
            ]:
                setattr(self, f"{skill}_level", data.get(f"{skill}_level", 1))
                setattr(self, f"{skill}_xp", data.get(f"{skill}_xp", 0))
                setattr(self, f"{skill}_max_xp", data.get(f"{skill}_max_xp", 150))

            # # Logs détaillés du sync
            # new_inv_total = sum(item.get("quantity", 0) for item in self.inventory if item.get("code")) if self.inventory else 0
            # if (old_x, old_y) != (self.x, self.y):
            #     print(f"[SYNC] Position: ({old_x}, {old_y}) → ({self.x}, {self.y})")
            # if (old_hp, old_max_hp) != (self.hp, self.max_hp):
            #     print(f"[SYNC] HP: {old_hp}/{old_max_hp} → {self.hp}/{self.max_hp}")
            # if old_level != self.level:
            #     print(f"[SYNC] Level: {old_level} → {self.level}")
            # if old_gold != self.gold:
            #     print(f"[SYNC] Gold: {old_gold} → {self.gold}")
            # if old_inv_total != new_inv_total:
            #     print(f"[SYNC] Inventaire: {old_inv_total} items → {new_inv_total} items ({self.inventory_max_items} max)")

            return True
        return False

    def inventory_is_full(self, margin: int = 5) -> bool:
        used = sum(
            item.get("quantity", 0) for item in self.inventory if item.get("code")
        )
        return (used + margin) >= self.inventory_max_items

    def attack(self):
        return self.fighter.attack()

    def gather(self):
        return self.gatherer.collect()

    def move(self, x, y):
        return self.mover.to_coords(x, y)

    def rest(self):
        return self.rester.rest()

    def craft(self, item_code: str, quantity: int = 1):
        return self.crafter.craft(item_code, quantity)

    def assign_task(self, task):
        self.default_task = None

    def __str__(self):
        return f"Name: {self.name} | {self.hp}/{self.max_hp} || {self.is_working} - {self.cooldown_expiration}"
