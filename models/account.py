import asyncio
from typing import Dict, Optional, Literal
from api.client import AsyncApiClient
from models.bank import BankManager
from models.item_manager import ItemsManager
from models.world import WorldMap
from models.character import Character
from models.task import Task, TaskResult, PendingRequest
from routines import gathering


class Account:
    def __init__(self, token: str):
        self.token = token
        self.client = AsyncApiClient(token=token)
        self.bank = BankManager(self.client)
        self.items_db = ItemsManager(self.client)
        self.world = WorldMap(self.client)
        self.characters: Dict[str, Character] = {}

        self.completion_queue: asyncio.Queue = asyncio.Queue()
        self.pending_tasks: Dict[int, Task] = {}
        self.children: Dict[int, list[Task]] = {}
        self.pending_requests: Dict[int, PendingRequest] = {}

        self._task_counter = 0
        self._char_rotation_index = 0
        self._request_counter = 0
        self.active_requests: set[tuple[str, str]] = set()

    def _make_priority_task(self, char: Character, target: str, quantity: int):
        def my_fn():
            return gathering(char, target, quantity)

        my_fn._action = "⚒️"
        my_fn._target = target
        return my_fn

    def _next_id(self) -> int:
        self._task_counter += 1
        return self._task_counter

    def _next_request_id(self) -> int:
        """Generate unique request ID."""
        self._request_counter += 1
        return self._request_counter

    def total_available(self, item_code: str) -> int:
        """
        1.1 Total available items: bank + all character inventories.
        Returns 0 if item not found.
        """
        total = self.bank.content.get(item_code, 0)

        for char in self.characters.values():
            for inv_item in char.inventory:
                if inv_item.get("code") == item_code:
                    total += inv_item.get("quantity", 0)

        return total

    def get_source(self, item_code: str) -> Optional[tuple[str, Optional[str]]]:
        """
        1.2 Determine item source: craftable, gatherable, or fight drop.
        Returns ("craft", skill), ("gather", None), ("fight", None), or None.
        """
        item = self.items_db.get_by_code(item_code)

        # Check if craftable first (items_db priority)
        if item and item.is_craftable:
            return ("craft", item.craft_skill)

        # Check if gatherable from world resources
        if hasattr(self.world, "resources") and self.world.resources:
            if item_code in self.world.resources:
                return ("gather", None)

            # Try alternative names
            alt_codes = [
                item_code + "s",
                item_code[:-1] if item_code.endswith("s") else None,
                item_code.replace("_ore", "_rocks"),
                item_code.replace("_rock", "_rocks"),
            ]
            for alt_code in alt_codes:
                if alt_code and alt_code in self.world.resources:
                    return ("gather", None)

        # If item exists but not craftable/gatherable, assume monster drop
        if item:
            return ("fight", None)

        # Item not found in any source
        return None

    def select_workers(
        self, source: tuple[str, Optional[str]], skill: Optional[str], requester: str
    ) -> list[str]:
        """
        1.3 Select appropriate workers based on source type and skill level.
        - fight → [requester] only
        - gather → filter by skill level
        - craft weapon/gear/jewel → [Kioyaa] only (dedicated crafter)
        - craft other → requester if skilled, else best available
        - Returns empty list if not enough skilled workers.
        """
        source_type, source_skill = source

        if source_type == "fight":
            return [requester]

        if source_type == "gather":
            return list(self.characters.keys())

        if source_type == "craft":
            requester_char = self.characters.get(requester)
            if not requester_char or not source_skill:
                return []

            requester_level = getattr(requester_char, f"{source_skill}_level", 0)
            if requester_level > 0:
                return [requester]

            for char_name, char in self.characters.items():
                char_level = getattr(char, f"{source_skill}_level", 0)
                if char_level > 0:
                    return [char_name]

            return []

        return []

    def build_task_queue(
        self,
        action: Literal[
            "gather", "fight", "craft", "deposit", "withdraw", "complete_task"
        ],
        target: str,
        quantity: int,
        inventory_max: int,
    ) -> list[Task]:
        """
        2.1 Build task queue with chunking based on inventory capacity.
        Includes deposit tasks after each chunk (Phase 2.1 spec).
        Returns list of Task objects with alternating action + deposit.
        """
        tasks = []
        task_list_id = self._next_id()

        chunks = quantity // inventory_max
        remainder = quantity % inventory_max

        # Full chunks: action + deposit
        for i in range(chunks):
            # Action task (gather/fight/craft)
            action_task = Task(
                id=self._next_id(),
                root_request_id=task_list_id,
                parent_id=None,
                type=action,  # type: ignore
                target=target,
                quantity=inventory_max,
                priority=10,
                required_skill=None,
                required_skill_level=0,
                required_materials=[],
                status="pending",
                assigned_to=None,
            )
            tasks.append(action_task)

            # Deposit task after collecting
            deposit_task = Task(
                id=self._next_id(),
                root_request_id=task_list_id,
                parent_id=action_task.id,
                type="deposit",
                target=target,
                quantity=inventory_max,
                priority=11,  # Slightly higher priority
                required_skill=None,
                required_skill_level=0,
                required_materials=[],
                status="pending",
                assigned_to=None,
            )
            tasks.append(deposit_task)

        # Remainder: action + deposit
        if remainder > 0:
            remainder_action = Task(
                id=self._next_id(),
                root_request_id=task_list_id,
                parent_id=None,
                type=action,  # type: ignore
                target=target,
                quantity=remainder,
                priority=10,
                required_skill=None,
                required_skill_level=0,
                required_materials=[],
                status="pending",
                assigned_to=None,
            )
            tasks.append(remainder_action)

            remainder_deposit = Task(
                id=self._next_id(),
                root_request_id=task_list_id,
                parent_id=remainder_action.id,
                type="deposit",
                target=target,
                quantity=remainder,
                priority=11,
                required_skill=None,
                required_skill_level=0,
                required_materials=[],
                status="pending",
                assigned_to=None,
            )
            tasks.append(remainder_deposit)

        return tasks

    async def listen_completions(self):
        while True:
            try:
                result = await asyncio.wait_for(self.completion_queue.get(), timeout=5)
            except asyncio.TimeoutError:
                await self._poll_gather_tasks()
                continue

            await self.on_task_complete(result)
            self.completion_queue.task_done()

    async def on_action(self, character: str, action_result: dict) -> None:
        """
        2.3 Handle character action completion.
        - Update character inventory
        - Check if pending requests can move forward (craft materials?)

        tasking() gère la livraison complète (withdraw + trade + complete)
        """
        char = self.characters.get(character)
        if not char:
            return

        if "inventory" in action_result:
            char.inventory = action_result["inventory"]

        action_type = action_result.get("action", "")

        if action_type in ["deposit", "gather", "fight", "craft"]:
            await self._check_pending_requests()

    async def _check_pending_requests(self) -> None:
        """
        Vérifier si les requêtes peuvent avancer:
        1. Pour gather/fight → attendre les tâches
        2. Pour craft → CRÉER craft tasks si matériaux disponibles
        """
        for request_id in list(self.pending_requests.keys()):
            req = self.pending_requests.get(request_id)
            if not req or req.status in ["completed", "blocked"]:
                continue

            if req.source[0] == "craft":
                all_ready = all(
                    self.total_available(code) >= qty
                    for code, qty in req.materials_pending.items()
                )

                if all_ready and req.status == "pending":
                    print(f"✅ Matériaux prêts pour craft: {req.target}")

                    workers = self.select_workers(
                        req.source, req.source[1], req.requester
                    )
                    if not workers:
                        print(f"⚠️ Aucun worker pour crafter {req.target}")
                        req.status = "blocked"
                        continue

                    req.assigned_workers = workers
                    quantity = req.quantity - self.total_available(req.target)

                    if quantity <= 0:
                        req.status = "in_progress"
                        print(f"✅ {req.target} déjà disponible, tasking() livrera")
                        continue

                    per_worker = quantity // len(workers)
                    remainder = quantity % len(workers)

                    for i, worker in enumerate(workers):
                        worker_qty = per_worker + (1 if i < remainder else 0)
                        craft_task = Task(
                            id=self._next_id(),
                            root_request_id=req.id,
                            parent_id=None,
                            type="craft",
                            target=req.target,
                            quantity=worker_qty,
                            priority=10,
                            required_skill=req.source[1],
                            required_skill_level=1,
                            required_materials=list(req.materials_pending.items()),
                            status="pending",
                            assigned_to=worker,
                            parent_request_id=req.id,
                        )
                        self.pending_tasks[craft_task.id] = craft_task
                        self.characters[worker].task_queue.put_nowait(craft_task)

                    req.status = "in_progress"
                    print(f"🔧 Craft tasks créés pour {req.target}")
                    continue

            if req.source[0] in ["fight", "gather"]:
                continue

    async def _fulfill_request(self, pending_request: PendingRequest) -> None:
        """
        DÉPRÉCIÉ: add_request() crée déjà gather/fight/craft/deposit directement.
        tasking() gère le withdraw/trade/complete_task.
        Cette fonction n'est plus utilisée.
        """
        pass

    async def _complete_pending_request(self, pending_request: PendingRequest) -> None:
        """
        Cleanup après que tasking() ait géré le rendu.
        IMPORTANT: Ne crée PAS withdraw/trade/complete_task.
        C'est tasking() qui gère tout ça directement.
        """
        pending_request.status = "completed"
        self.pending_requests.pop(pending_request.id, None)

        for requester in pending_request.requesters:
            self.active_requests.discard((pending_request.target, requester))

        print(f"✅ Requête {pending_request.target} complétée et nettoyée")

    async def add_request(
        self, target: str, quantity: int, requester: str
    ) -> Optional[PendingRequest]:
        """
        Résolution complète d'une requête:
        1. Si requête en cours → join existing
        2. Si ressources dispo → mark as completed (tasking() s'occupe de la livraison)
        3. Si materiel → resolve recursively + wait + craft
        4. Sinon → gather/fight tasks

        IMPORTANT: Vérifier existing_request AVANT active_requests pour éviter les doublons!
        """
        # =====================================================================
        # 1. Check for EXISTING request (completed ou en cours)
        # =====================================================================
        existing_request = None
        for req in self.pending_requests.values():
            if req.target == target and req.status not in ["blocked"]:
                existing_request = req
                break

        # Si requête existe et pas complétée → ajouter le requester
        if existing_request and existing_request.status != "completed":
            if requester not in existing_request.requesters:
                existing_request.requesters.append(requester)
            print(f"➕ {requester} ajouté à la requête existante pour {target}")
            return existing_request

        # Si requête existe et EST complétée → ne rien faire, tasking() la gère
        if existing_request and existing_request.status == "completed":
            print(f"✅ {target} déjà en cours de livraison par tasking()")
            return None

        # =====================================================================
        # 2. Check if already being created by another concurrent call
        # =====================================================================
        if (target, requester) in self.active_requests:
            print(f"⏳ {requester} — Requête {target} déjà en création, patienter...")
            return None

        # Lock this request creation
        self.active_requests.add((target, requester))

        try:
            available = self.total_available(target)

            # =====================================================================
            # 3. Check if resources exist (ONLY for craft, not gather/fight)
            # =====================================================================
            # For gather/fight: need to CREATE TASKS even if resources exist!
            # Because someone must actively go collect them.
            source = self.get_source(target)
            if not source:
                print(f"❌ Source introuvable pour {target}")
                return None

            # ONLY mark as "completed" for craft items that already exist
            # gather/fight MUST create tasks because they're active actions
            if available >= quantity and source[0] == "craft":
                pending = PendingRequest(
                    id=self._next_request_id(),
                    target=target,
                    quantity=quantity,
                    requester=requester,
                    requesters=[requester],
                    source=source,
                    status="completed",
                )
                self.pending_requests[pending.id] = pending
                print(f"✅ {target} déjà crafté ({available}), tasking() livrera")
                return None

            # =====================================================================
            # 4. Check if requester already has another pending request
            # =====================================================================
            for req in self.pending_requests.values():
                if req.requester == requester and req.status != "completed":
                    print(f"⚠️ {requester} a déjà une requête en cours")
                    return None

            pending_request = PendingRequest(
                id=self._next_request_id(),
                target=target,
                quantity=quantity,
                requester=requester,
                requesters=[requester],
                source=source,
                status="pending",
            )

            if source[0] == "craft":
                item = self.items_db.get_by_code(target)
                if item and item.craft_ingredients:
                    for material in item.craft_ingredients:
                        mat_qty = material["quantity"] * quantity
                        # Récursivement ajouter la requête matériau
                        await self.add_request(material["code"], mat_qty, requester)
                        pending_request.materials_pending[material["code"]] = mat_qty

                pending_request.status = "pending"
                self.pending_requests[pending_request.id] = pending_request
                print(
                    f"⏳ Requête craft créée (attent matériaux): {quantity}x {target}"
                )
                return pending_request

            if source[0] in ["gather", "fight"]:
                workers = self.select_workers(source, source[1], requester)
                if not workers:
                    print(f"⚠️ Aucun worker compétent pour {target}")
                    return None

                to_farm = quantity - available
                per_worker = to_farm // len(workers)
                remainder = to_farm % len(workers)

                pending_request.assigned_workers = workers
                pending_request.status = "pending"

                for i, worker in enumerate(workers):
                    worker_qty = per_worker + (1 if i < remainder else 0)
                    tasks = self.build_task_queue(
                        source[0],  # type: ignore
                        target,
                        worker_qty,
                        self.characters[worker].inventory_max_items,
                    )
                    for task in tasks:
                        task.assigned_to = worker
                        task.parent_request_id = pending_request.id
                        self.pending_tasks[task.id] = task
                        # 🔥 ASSIGN TASK TO WORKER'S QUEUE IMMEDIATELY
                        self.characters[worker].task_queue.put_nowait(task)

            self.pending_requests[pending_request.id] = pending_request
            print(f"✅ Requête créée : {quantity}x {target} pour {requester}")
            return pending_request

        except Exception as e:
            print(f"❌ Erreur dans add_request({target}, {quantity}, {requester}): {e}")
            return None
        finally:
            # Nettoyer active_requests pour permettre les appels futurs de trouver la requête créée
            self.active_requests.discard((target, requester))

    async def on_task_complete(self, result: TaskResult):
        """
        Après qu'une tâche soit complétée:
        1. Créer la deposit task
        2. Vérifier si les requêtes peuvent avancer (craft materials?)
        """
        task = self.pending_tasks.get(result.task_id)
        if not task:
            return

        await self.bank.sync()

        if task.type in ["gather", "fight", "craft"] and result.success:
            deposit_task = Task(
                id=self._next_id(),
                root_request_id=task.root_request_id,
                parent_id=task.id,
                type="deposit",
                target=task.target,
                quantity=task.quantity,
                priority=11,
                required_skill=None,
                required_skill_level=0,
                required_materials=[],
                status="pending",
                assigned_to=task.assigned_to,
                parent_request_id=task.parent_request_id,
            )
            self.pending_tasks[deposit_task.id] = deposit_task
            if task.assigned_to:
                self.characters[task.assigned_to].task_queue.put_nowait(deposit_task)

        await self._check_pending_requests()

        enfants = self.children.get(task.id, [])
        non_done = [t for t in enfants if t.status not in ["done", "cancelled"]]

        if not non_done and task.parent_id is not None:
            parent = self.pending_tasks.get(task.parent_id)
            if parent:
                self.children[parent.id] = [
                    t
                    for t in self.children.get(parent.id, [])
                    if t.status not in ["done", "cancelled"]
                ]
                await self.try_assign_or_expand(parent)

    async def initialize(self):
        await asyncio.gather(
            self.items_db.load_or_update(),
            self.bank.sync(),
            self.world.init_map(),
        )

    def add_character(self, name: str) -> Character:
        char = Character(name=name, account=self)
        self.characters[name] = char
        return char

    async def assign_task(self, task: Task):

        candidats = [
            char
            for char in self.characters.values()
            if task.required_skill is None
            or getattr(char, f"{task.required_skill}_level", 0)
            >= task.required_skill_level
        ]

        if not candidats:
            task.status = "pending"
            print(f"⏳ Aucun personnage avec le skill requis pour {task.target}")
            return

        def occupation_score(char):
            if char.priority_task is None and char.task_queue.empty():
                return 0  # complètement libre
            if char.priority_task is None:
                return 1  # queue non vide mais pas de priority
            return 2  # déjà une priority_task

        selected = min(candidats, key=occupation_score)

        task.assigned_to = selected.name

        if task.type == "gather":
            task.status = "running"
            selected.priority_task = self._make_priority_task(
                selected, task.target, task.quantity
            )
        else:
            task.status = "assigned"
            selected.assign_task(task)

        print(f"📋 {task.type} {task.target} x{task.quantity} → {selected.name}")

    async def try_assign_or_expand(self, task: Task):
        item = self.items_db.get_by_code(task.target)
        if not item:
            print(f"❌ Item '{task.target}' introuvable.")
            return

        if task.type == "gather":
            await self.assign_task(task)
            return

        if not item.is_craftable:
            print(f"❌ '{task.target}' n'est pas craftable.")
            return

        missings = task.missing_materials(self.bank.content)

        if missings:
            for miss in missings:
                mat_item = self.items_db.get_by_code(miss["code"])
                sous_type = "craft" if mat_item and mat_item.is_craftable else "gather"

                existing = next(
                    (
                        t
                        for t in self.children.get(task.id, [])
                        if t.target == miss["code"]
                        and t.type == sous_type
                        and t.status not in ["done", "cancelled"]
                    ),
                    None,
                )
                if existing:
                    continue

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

    async def cancel_request(self, root_request_id: int):
        tasks = [
            t
            for t in self.pending_tasks.values()
            if t.root_request_id == root_request_id
        ]

        if not tasks:
            print(f"❌ Requête {root_request_id} introuvable.")
            return

        for task in tasks:
            if task.assigned_to and task.status in ["assigned", "running"]:
                char = self.characters.get(task.assigned_to)
                if char:
                    char.priority_task = None
                    current = getattr(char, "_current_task", None)
                    if current and not current.done():
                        current.cancel()

            task.cancel()
            self.pending_tasks.pop(task.id, None)
        self.children = {
            k: v for k, v in self.children.items() if k not in {t.id for t in tasks}
        }

        print(f"🗑️ Requête {root_request_id} annulée ({len(tasks)} tâches supprimées).")
