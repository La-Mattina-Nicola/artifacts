import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, TYPE_CHECKING
from models.actions import MoveAction, FightAction, RestAction, GatherAction

if TYPE_CHECKING:
    from models.account import Account


class CharacterBankInterface:
    """Interface personnelle pour interagir avec le BankManager partagé."""

    def __init__(self, char, shared_manager):
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
    account: Any

    level: int = 1
    hp: int = 0
    max_hp: int = 0
    x: int = 0
    y: int = 0
    gold: int = 0
    inventory_max_items: int = 20
    inventory: List[Dict[str, Any]] = field(default_factory=list, repr=False)

    def __post_init__(self):
        # Récupération des ressources via l'account parent
        self.client = self.account.client
        self.world_map = self.account.world
        self.items_db = self.account.items_db

        # Interface de banque dédiée
        self.banker = CharacterBankInterface(self, self.account.bank)

        # File d'attente et routine
        self.task_queue = asyncio.Queue()
        self.default_task = None

        # Modules d'actions
        self.mover = MoveAction(self)
        self.fighter = FightAction(self)
        self.rest_manager = RestAction(self)
        self.gatherer = GatherAction(self)

    async def main_loop(self):
        print(f"🚀 {self.name} en ligne.")
        while True:
            try:
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
                await asyncio.sleep(5)
            await asyncio.sleep(2)

    async def sync(self):
        response = await self.client.get(f"/characters/{self.name}")
        if response.status_code == 200:
            data = response.json()["data"]
            self.x, self.y = data["x"], data["y"]
            self.hp, self.max_hp = data["hp"], data["max_hp"]
            self.level, self.gold = data["level"], data["gold"]
            self.inventory = data["inventory"]
            self.inventory_max_items = data["inventory_max_items"]
            self.client.cooldown_expiration = data["cooldown_expiration"]
            print(f"🔄 {self.name} synchronisé.")
            return True
        return False

    def inventory_is_full(self, margin: int = 5) -> bool:
        used = sum(
            item.get("quantity", 0) for item in self.inventory if item.get("code")
        )
        return (used + margin) >= self.inventory_max_items
