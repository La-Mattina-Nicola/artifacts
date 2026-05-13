import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, TYPE_CHECKING
from datetime import datetime, timezone
from models.tasks import Task
import inspect

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
    task = None
    task_type = None
    task_progress = 0
    task_total = 0
    weapon_slot: str = ""
    rune_slot: str = ""
    shield_slot: str = ""
    helmet_slot: str = ""
    body_armor_slot: str = ""
    leg_armor_slot: str = ""
    boots_slot: str = ""
    ring1_slot: str = ""
    ring2_slot: str = ""
    amulet_slot: str = ""
    artifact1_slot: str = ""
    artifact2_slot: str = ""
    artifact3_slot: str = ""
    utility1_slot: str = ""
    utility1_slot_quantity: int = 0
    utility2_slot: str = ""
    utility2_slot_quantity: int = 0
    bag_slot: str = ""

    def __post_init__(self):
        from api.client import AsyncApiClient
        from models.actions import (
            MoveAction,
            FightAction,
            RestAction,
            GatherAction,
            CraftAction,
            TaskAction,
            EquipAction,
        )

        self.client = AsyncApiClient(token=self.account.token, character=self)
        self.world_map = self.account.world
        self.items_db = self.account.items_db
        self.banker = CharacterBankInterface(self, self.account.bank)
        self.mover = MoveAction(self)
        self.fighter = FightAction(self)
        self.rester = RestAction(self)
        self.gatherer = GatherAction(self)
        self.crafter = CraftAction(self)
        self.tasker = TaskAction(self)
        self.equiper = EquipAction(self)

        self.task_queue = asyncio.Queue()
        self.todo_queue = asyncio.Queue()
        self.todo_task = None
        self.priority_task = None
        self.default_task = None

        self.paused = False

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
        self.task = data.get("task", self.task)
        self.task_type = data.get("task_type", self.task_type)
        self.task_progress = data.get("task_progress", self.task_progress)
        self.task_total = data.get("task_total", self.task_total)
        self.weapon_slot = data.get("weapon_slot", self.weapon_slot)
        self.rune_slot = data.get("rune_slot", self.rune_slot)
        self.shield_slot = data.get("shield_slot", self.shield_slot)
        self.helmet_slot = data.get("helmet_slot", self.helmet_slot)
        self.body_armor_slot = data.get("body_armor_slot", self.body_armor_slot)
        self.leg_armor_slot = data.get("leg_armor_slot", self.leg_armor_slot)
        self.boots_slot = data.get("boots_slot", self.boots_slot)
        self.ring1_slot = data.get("ring1_slot", self.ring1_slot)
        self.ring2_slot = data.get("ring2_slot", self.ring2_slot)
        self.amulet_slot = data.get("amulet_slot", self.amulet_slot)
        self.artifact1_slot = data.get("artifact1_slot", self.artifact1_slot)
        self.artifact2_slot = data.get("artifact2_slot", self.artifact2_slot)
        self.artifact3_slot = data.get("artifact3_slot", self.artifact3_slot)
        self.utility1_slot = data.get("utility1_slot", self.utility1_slot)
        self.utility1_slot_quantity = data.get(
            "utility1_slot_quantity", self.utility1_slot_quantity
        )
        self.utility2_slot = data.get("utility2_slot", self.utility2_slot)
        self.utility2_slot_quantity = data.get(
            "utility2_slot_quantity", self.utility2_slot_quantity
        )
        self.bag_slot = data.get("bag_slot", self.bag_slot)

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
            self.task = data.get("task")
            self.task_type = data.get("task_type")
            self.task_progress = data.get("task_progress", 0)
            self.task_total = data.get("task_total", 0)

            self.weapon_slot = data.get("weapon_slot", "")
            self.rune_slot = data.get("rune_slot", "")
            self.shield_slot = data.get("shield_slot", "")
            self.helmet_slot = data.get("helmet_slot", "")
            self.body_armor_slot = data.get("body_armor_slot", "")
            self.leg_armor_slot = data.get("leg_armor_slot", "")
            self.boots_slot = data.get("boots_slot", "")
            self.ring1_slot = data.get("ring1_slot", "")
            self.ring2_slot = data.get("ring2_slot", "")
            self.amulet_slot = data.get("amulet_slot", "")
            self.artifact1_slot = data.get("artifact1_slot", "")
            self.artifact2_slot = data.get("artifact2_slot", "")
            self.artifact3_slot = data.get("artifact3_slot", "")
            self.utility1_slot = data.get("utility1_slot", "")
            self.utility1_slot_quantity = data.get("utility1_slot_quantity", 0)
            self.utility2_slot = data.get("utility2_slot", "")
            self.utility2_slot_quantity = data.get("utility2_slot_quantity", 0)
            self.bag_slot = data.get("bag_slot", "")

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

            return True
        return False

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

    async def _run_tasklike(self, tasklike) -> bool:
        if tasklike is None:
            return False

        try:
            # 1. Si c'est déjà une coroutine → on l'attend
            if inspect.iscoroutine(tasklike):
                await tasklike
                return True

            # 2. Si c'est un objet Task interne
            if isinstance(tasklike, Task):
                await self._execute(tasklike)
                return True

            # 3. Si c'est un callable (lambda, partial, fonction)
            if callable(tasklike):
                result = tasklike()  # exécute la lambda / partial

                # 3a. Si le résultat est une coroutine → on l'attend
                if inspect.iscoroutine(result):
                    await result

                # 3b. Si c'est sync → rien à await
                return True

            print(f"⚠️ _run_tasklike: objet non exécutable : {tasklike}")
            return False

        except Exception as e:
            print(f"❌ Erreur dans _run_tasklike : {e}")
            return False

    async def main_loop(self):
        await asyncio.sleep(1)

        while True:
            try:
                await self.wait_until_ready()

                # Récupérer une task si aucune en cours
                if self.todo_task is None and not self.todo_queue.empty():
                    self.todo_task = await self.todo_queue.get()

                # PRIORITÉ
                if self.priority_task is not None:
                    await self._run_tasklike(self.priority_task)
                    self.priority_task = None

                # TASK NORMALE
                elif self.todo_task is not None:
                    await self._run_tasklike(self.todo_task)

                    # Marquer la task comme DONE si elle existe dans pending_tasks
                    if hasattr(self.todo_task, "__task_id__"):
                        task_id = self.todo_task.__task_id__
                        self.account.pending_tasks[task_id].status = "done"

                    self.todo_task = None

                # DEFAULT TASK
                elif self.default_task:
                    await self._run_tasklike(self.default_task)

                else:
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"❌ Erreur dans main_loop : {e}")

    def inventory_is_full(self, margin: int = 5) -> bool:
        used = sum(
            item.get("quantity", 0) for item in self.inventory if item.get("code")
        )
        return (used + margin) >= self.inventory_max_items

    def inventory_quantity(self, item_code: str) -> int:
        return sum(
            item.get("quantity", 0)
            for item in self.inventory
            if item.get("code") == item_code
        )

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

    async def _execute(self, task):
        from routines import crafting, gathering, fighting

        if task.type == "craft":
            await crafting(self, task.target, task.quantity_total)
        if task.type == "gather":
            await gathering(self, task.target, task.quantity_total)
        if task.type == "fight":
            await fighting(self, task.target, task.quantity_total)
        if task.type == "items":
            await self.account.ensure_resource(task.target, task.quantity_total, self)
        if task.type in ["craft", "gather", "fight", "items"]:
            task.status = "done"
            return True

    def get_skill_level(self, skill: str) -> int:
        return getattr(self, f"{skill}_level", 1)

    def can_gather(self, sources) -> bool:
        return any(self.get_skill_level(s.skill) >= s.level for s in sources)

    def best_gather_source(self, sources):
        """Retourne la meilleure source accessible, ou None."""
        viable = [s for s in sources if self.get_skill_level(s.skill) >= s.level]
        return min(viable, key=lambda s: s.level) if viable else None

    def can_craft(self, item) -> bool:
        if not item.craft:
            return False
        return self.get_skill_level(item.craft["skill"]) >= item.craft["level"]

    def is_equipped_with_best_tool_for_skill(self, skill: str) -> bool:
        best_tool = self.account.items_db.get_best_tool_for_skill(skill, self)
        if not best_tool:
            return True  # pas d'outil requis
        return any(
            inv_item.get("code") == best_tool.code for inv_item in self.inventory
        )

    async def equip_best_tool_for_skill(self, skill: str):
        best_tool = self.account.items_db.get_best_tool_for_skill(skill, self)
        # check if already equipped
        print(self.weapon_slot)

        print(f"Best tool for {skill}: {best_tool.code if best_tool else 'None'}")

        if best_tool.code != self.weapon_slot:
            await self.mover.to_bank()
            await self.equiper.unequip(slot="weapon")
            await self.banker.withdraw([{"code": best_tool.code, "quantity": 1}])
            await self.equiper.equip(best_tool.code, slot="weapon")
            await self.sync()

    def __str__(self):
        return f"Name: {self.name} | {self.hp}/{self.max_hp} || {self.is_working} - {self.cooldown_expiration}"
