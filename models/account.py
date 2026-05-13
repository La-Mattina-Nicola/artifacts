import asyncio
import itertools
from typing import Dict
from api.client import AsyncApiClient
from models.bank import BankManager
from models.item_manager import ItemsManager
from models.world import WorldMap
from models.character import Character
from models import ResourceManager
from models import Task
from routines import gathering, fighting, crafting
from functools import partial


class Account:
    def __init__(self, token: str):
        self.token = token
        self.client = AsyncApiClient(token=token)
        self.bank = BankManager(self.client)
        self.items_db = ItemsManager(self.client)
        self.world = WorldMap(self.client)
        self.resources = ResourceManager(self.client)
        self.characters: Dict[str, Character] = {}

        self.completion_queue: asyncio.Queue = asyncio.Queue()
        self.pending_tasks: Dict[str, Task] = {}

        self._task_id_counter = itertools.count(1)

    async def initialize(self):
        print("Before init ...")
        await asyncio.gather(
            self.items_db.load_or_update(),
            self.bank.sync(),
            self.world.init_map(),
            self.resources.init(),
        )
        print("After init ...")

    def add_character(self, name: str) -> Character:
        char = Character(name=name, account=self)
        self.characters[name] = char
        return char

    async def listen_completions(self):
        while True:
            try:
                result = await asyncio.wait_for(self.completion_queue.get(), timeout=5)
            except asyncio.TimeoutError:
                continue

            await self.on_task_complete(result)
            self.completion_queue.task_done()

    def create_task(
        self, type, target, quantity_total, skill=None, skill_level=None, parent_id=0
    ):
        task_id = next(self._task_id_counter)
        task = Task(
            id=task_id,
            type=type,
            target=target,
            quantity_total=quantity_total,
            skill=skill,
            skill_level=skill_level,
            parent_id=parent_id,
        )
        self.pending_tasks[task_id] = task
        return task

    # ---------------------------------------------------------
    #  ENSURE RESOURCE (fonction principale)
    # ---------------------------------------------------------
    async def ensure_resource(self, code, needed, requester):
        bank_qty = self.bank.quantity(code)
        if bank_qty >= needed:
            return

        item = self.items_db.get_by_code(code)

        # 1. Craftable
        if item and item.craft:
            if not requester.can_craft(item):
                raise Exception(
                    f"{requester.name} niveau {item.craft['skill']} insuffisant "
                    f"({requester.get_skill_level(item.craft['skill'])} < {item.craft['level']}) "
                    f"pour crafter '{code}'"
                )
            task = self.create_task(
                "craft",
                code,
                needed,
                skill=item.craft["skill"],
                skill_level=item.craft["level"],
            )
            return await self.ensure_craft(task, requester)

        # 2. Gatherable (via ResourceManager)
        sources = self.resources.get_resource_objects_for_item(code)
        if sources:
            if not requester.can_gather(sources):
                best = min(sources, key=lambda s: s.level)
                raise Exception(
                    f"{requester.name} niveau {best.skill} insuffisant "
                    f"({requester.get_skill_level(best.skill)} < {best.level}) "
                    f"pour collecter '{code}'"
                )
            task = self.create_task("gather", code, needed)
            return await self.ensure_gather(task, requester)

        # 3. Monster drop
        if item and item.type == "monster_drop":
            task = self.create_task("fight", code, needed)
            return await self.ensure_fight(task, requester)

        raise Exception(f"Impossible de déterminer comment obtenir {code}")

    # ---------------------------------------------------------
    #  GATHER
    # ---------------------------------------------------------
    async def ensure_gather(self, task: Task, requester: Character):
        task.status = "running"
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await gathering(requester, task.target, task.quantity_total)
                task.status = "done"
                return
            except Exception as e:
                print(f"⚠️ Tentative {attempt + 1}/{max_retries} échouée: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                else:
                    task.status = "failed"
                    raise

    # Idem pour ensure_fight
    async def ensure_fight(self, task: Task, requester: Character):
        task.status = "running"
        await fighting(requester, task.target, task.quantity_total)
        task.status = "done"

    # Et le bug copier-coller dans ensure_craft
    async def ensure_craft(self, task: Task, requester: Character):
        item = self.items_db.get_by_code(task.target)

        skill = item.craft["skill"]
        required_level = item.craft["level"]

        if requester.get_skill_level(skill) < required_level:
            raise Exception(
                f"{requester.name} niveau {skill} insuffisant "
                f"({requester.get_skill_level(skill)} < {required_level}) "
                f"pour crafter '{task.target}'"
            )
        recipe = item.craft["items"]

        # Sous-tâches
        for ing in recipe:
            ing_code = ing["code"]
            ing_qty = ing["quantity"] * task.quantity_total
            await self.ensure_resource(ing_code, ing_qty, requester)
        task.status = "running"
        await crafting(
            requester, task.target, task.quantity_total
        )  # ← était fighting !
        task.status = "done"
