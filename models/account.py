import asyncio
from typing import Dict
from api.client import AsyncApiClient
from models.bank import BankManager
from models.item_manager import ItemsManager
from models.world import WorldMap
from models.character import Character


class Account:
    def __init__(self, token: str):
        self.token = token  # Stocker le token[cite: 2]
        self.client = AsyncApiClient(
            token=token
        )  # Client "maître" pour les infos globales
        self.bank = BankManager(self.client)
        self.items_db = ItemsManager(self.client)
        self.world = WorldMap(self.client)
        self.characters: Dict[str, Character] = {}

    def add_character(self, name: str) -> Character:
        # Le personnage créera son propre client dans son __post_init__[cite: 1, 2]
        char = Character(name=name, account=self)
        self.characters[name] = char
        return char

    async def initialize(self):
        """Initialise les données globales avant de lancer les personnages."""
        # On utilise asyncio.gather pour tout lancer en parallèle
        await asyncio.gather(
            self.items_db.update(),  # Modifié ici : load_or_update -> update
            self.bank.sync(),
            self.world.init_map(),
        )
