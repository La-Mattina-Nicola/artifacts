import asyncio
from typing import Dict
from api.client import AsyncApiClient
from models.bank import BankManager
from models.item_manager import ItemsManager
from models.world import WorldMap
from models.character import Character
from models.task import Task, TaskResult
from routines import gathering


class Account:
    def __init__(self, token: str):
        self.token = token
        self.client = AsyncApiClient(token=token)
        self.bank = BankManager(self.client)
        self.items_db = ItemsManager(self.client)
        self.world = WorldMap(self.client)
        self.characters: Dict[str, Character] = {}

        # Nouveaux attributs
        self.completion_queue: asyncio.Queue = asyncio.Queue()
        self.pending_tasks: Dict[int, Task] = {}
        self.children: Dict[int, list[Task]] = {}

        self._task_counter = 0
        self._char_rotation_index = 0

    def _make_priority_task(self, char: Character, target: str, quantity: int):
        def my_fn():
            return gathering(char, target, quantity)

        my_fn._action = "⚒️"
        my_fn._target = target
        return my_fn

    def _next_id(self) -> int:
        self._task_counter += 1
        return self._task_counter

    async def listen_completions(self):
        while True:
            try:
                result = await asyncio.wait_for(self.completion_queue.get(), timeout=5)
            except asyncio.TimeoutError:
                await self._poll_gather_tasks()
                continue

            await self.on_task_complete(result)
            self.completion_queue.task_done()

    async def _poll_gather_tasks(self):
        await asyncio.sleep(60)
        await self.bank.sync()

        for task in self.pending_tasks.values():
            if task.type != "gather" or task.status != "running":
                continue

            char_name = task.assigned_to
            if not char_name:
                continue

            char = self.characters.get(char_name)
            if not char:
                continue

            gathered = self.bank.content.get(task.target, 0)
            if gathered < task.quantity:
                continue

            char.priority_task = None
            task.mark_done()
            await self.completion_queue.put(
                TaskResult(task_id=task.id, character=char, success=True)
            )

    async def on_task_complete(self, result: TaskResult):
        task = self.pending_tasks.get(result.task_id)
        if not task:
            return

        await self.bank.sync()

        print(f"✅ Task {task.type} {task.target} terminée par {result.character.name}")

        # Regarder les enfants de cette tâche
        enfants = self.children.get(task.id, [])
        non_done = [t for t in enfants if t.status != "done"]

        if not non_done:
            # Tous les enfants sont done → réévaluer le parent
            if task.parent_id is not None:
                parent = self.pending_tasks.get(task.parent_id)
                if parent:
                    await self.try_assign_or_expand(parent)
        # sinon on attend les autres enfants

    async def initialize(self):
        await asyncio.gather(
            self.items_db.load_or_update(),
            self.bank.sync(),
            self.world.init_map(),
        )

    def add_character(self, name: str) -> Character:
        # Le personnage créera son propre client dans son __post_init__
        char = Character(name=name, account=self)
        self.characters[name] = char
        return char

    async def assign_task(self, task: Task):
        chars = list(self.characters.values())

        if not chars:
            return

        # 🔁 rotation
        start_index = self._char_rotation_index
        n = len(chars)

        selected = None

        # 1️⃣ priorité → perso dispo
        for i in range(n):
            idx = (start_index + i) % n
            char = chars[idx]

            if not char.is_working:
                selected = char
                self._char_rotation_index = (idx + 1) % n
                break

        # 2️⃣ fallback → tous occupés → on prend quand même le prochain
        if not selected:
            selected = chars[start_index]
            self._char_rotation_index = (start_index + 1) % n

        if not selected:
            task.status = "pending"
            print(f"⏳ Aucun personnage dispo pour {task.target}")
            return

        task.assigned_to = selected.name

        if task.type == "gather":
            task.status = "running"
            selected.priority_task = self._make_priority_task(selected, task.target)
            print(
                f"📋 {task.type} {task.target} x{task.quantity} assigné à {selected.name}"
            )
            return

        task.status = "assigned"
        selected.assign_task(task)
        print(
            f"📋 {task.type} {task.target} x{task.quantity} assigné à {selected.name}"
        )

    async def try_assign_or_expand(self, task: Task):
        item = self.items_db.get_by_code(task.target)
        if not item:
            print(f"❌ Item '{task.target}' introuvable.")
            return

        # Tâche gather → assigner directement
        if task.type == "gather":
            await self.assign_task(task)
            return

        # Tâche craft → vérifier les matériaux
        if not item.is_craftable:
            print(f"❌ '{task.target}' n'est pas craftable.")
            return

        missings = task.missing_materials(self.bank.content)

        if missings:
            for miss in missings:
                mat_item = self.items_db.get_by_code(miss["code"])
                sous_type = "craft" if mat_item and mat_item.is_craftable else "gather"

                sous_tache = Task(
                    id=self._next_id(),
                    root_request_id=task.root_request_id,
                    parent_id=task.id,
                    type=sous_type,
                    target=miss["code"],
                    quantity=miss["quantity"],
                    priority=task.priority - 1,
                    required_skill=mat_item.craft_skill
                    if sous_type == "craft"
                    else None,
                    required_skill_level=mat_item.craft_level
                    if sous_type == "craft"
                    else 0,
                    required_materials=mat_item.craft_ingredients
                    if sous_type == "craft"
                    else [],
                    status="pending",
                    assigned_to=None,
                )

                self.pending_tasks[sous_tache.id] = sous_tache
                self.children.setdefault(task.id, []).append(sous_tache)
                await self.try_assign_or_expand(sous_tache)
            return

        await self.assign_task(task)

    async def add_request(self, target: str, quantity: int = 1, priority: int = 10):
        item = self.items_db.get_by_code(target)
        if not item:
            print(f"❌ Item '{target}' introuvable.")
            return

        task_id = self._next_id()
        task_type = "craft" if item.is_craftable else "gather"
        task = Task(
            id=task_id,
            root_request_id=task_id,
            parent_id=None,
            type=task_type,
            target=target,
            quantity=quantity,
            priority=priority,
            required_skill=item.craft_skill if item.is_craftable else None,
            required_skill_level=item.craft_level if item.is_craftable else 0,
            required_materials=item.craft_ingredients if item.is_craftable else [],
            status="pending",
            assigned_to=None,
        )

        self.pending_tasks[task.id] = task
        self.children[task.id] = []
        if task.type == "gather":
            await self.assign_task(task)
        else:
            await self.try_assign_or_expand(task)
        print(f"✅ Requête ajoutée : {quantity}x {target} (priorité {priority})")
