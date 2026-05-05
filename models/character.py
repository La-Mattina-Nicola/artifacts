import asyncio
from .actions import MoveAction, FightAction  # On va le créer juste après


class Character:
    def __init__(self, name, client, world_map):
        self.name = name
        self.client = client
        self.world_map = world_map

        # État du personnage (sera rempli par sync())
        self.x = 0
        self.y = 0
        self.cooldown = 0
        self.next_free_slot = 0  # Utilisé par le décorateur @auto_cooldown
        self.skills = {}
        self.inventory = []

        # Modules d'actions
        self.mover = MoveAction(self)
        self.fighter = FightAction(self)
        # self.gatherer = GatherAction(self) <-- Prochainement

    async def sync(self):
        response = await self.client.get(f"/characters/{self.name}")
        if response.status_code == 200:
            data = response.json()["data"]
            self.x = data["x"]
            self.y = data["y"]
            self.hp = data["hp"]
            # On passe la date d'expiration directement au client
            self.client.cooldown_expiration = data.get("cooldown_expiration")
            print(
                f"🔄 {self.name} synchronisé. Prochaine action possible à : {self.client.cooldown_expiration}"
            )
