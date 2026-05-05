import asyncio
from typing import Dict
from api.client import AsyncApiClient
from models.bank import BankManager
from models.item_manager import ItemsManager
from models.world import WorldMap
from models.character import Character


class Account:
    def __init__(self, token: str):
        self.client = AsyncApiClient(token=token)
        self.bank = BankManager(self.client)
        self.items_db = ItemsManager(self.client)
        self.world = WorldMap(self.client)
        self.characters: Dict[str, Character] = {}

    async def initialize(self):
        """Initialise les données globales avant de lancer les personnages."""
        # On utilise asyncio.gather pour tout lancer en parallèle
        await asyncio.gather(
            self.items_db.update(),  # Modifié ici : load_or_update -> update
            self.bank.sync(),
            self.world.init_map(),
        )

    def add_character(self, name: str) -> Character:
        """Crée un personnage lié à ce compte."""
        char = Character(name=name, account=self)
        self.characters[name] = char
        return char
