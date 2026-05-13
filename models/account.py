import asyncio
from typing import Dict
from api.client import AsyncApiClient
from models.bank import BankManager
from models.item_manager import ItemsManager
from models.world import WorldMap
from models.character import Character
from models import ResourceManager
from models import Task
from routines import gathering, fighting


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
        self.pending_tasks: Dict[int, Task] = {}

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
        # Le personnage créera son propre client dans son __post_init__
        char = Character(name=name, account=self)
        self.characters[name] = char
        return char

    async def is_task_doable(self, requester: Character, type: str) -> bool:
        if type == "items":
            if self.bank.enough_in_bank(requester.task, requester.task_total):
                return True
            else:
                get_item = self.items_db.get_by_code(requester.task)
                if get_item.craft is None:
                    gather_task = Task(
                        id=1,
                        type="gather",
                        skill=get_item.subtype,
                        skill_level=get_item.level,
                        target=requester.task,
                        status="pending",
                        assigned_to=None,
                        quantity=requester.task_total
                        - self.bank.content.get(requester.task, 0),
                    )
                    self.pending_tasks[gather_task.id] = gather_task
                    print(
                        f"⚠️ Tâche {requester.task} non réalisable. Création d'une tâche de collecte pour {gather_task.quantity}x {gather_task.target}."
                    )

                    eligible_char = gather_task.find_eligible_character(
                        self.characters, get_item.subtype, get_item.level
                    )
                    if eligible_char:
                        eligible = eligible_char[0]
                        if requester.name in [char.name for char in eligible_char]:
                            eligible = requester
                        gather_task.assigned_to = eligible.name
                        gather_task.status = "assigned"
                        print(
                            f"✅ Tâche de collecte pour {gather_task.target} assignée à {eligible.name}."
                        )
                        self.characters[eligible.name].task_queue.put_nowait(
                            lambda: gathering(
                                eligible, gather_task.target, requester.task_total
                            )
                        )
                    else:
                        print(
                            f"⚠️ Aucun personnage éligible trouvé pour la tâche de collecte de {gather_task.target}."
                        )
                    return False
                else:
                    # get all required items for the craft and check if we have them in the bank, if not create gather tasks for them

                    pass

            pass
        else:
            # find where the monster is located on the map and if we can access it
            requester.task_queue.put_nowait(lambda: fighting(requester, requester.task))
            return False
        return True

    async def listen_completions(self):
        while True:
            try:
                result = await asyncio.wait_for(self.completion_queue.get(), timeout=5)
            except asyncio.TimeoutError:
                continue

            await self.on_task_complete(result)
            self.completion_queue.task_done()
