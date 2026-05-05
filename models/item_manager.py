import json
import os
from typing import Dict, List, Optional

from models.items import Item


class ItemsManager:
    def __init__(self, client, cache_file="data/items.json"):
        self.client = client
        self.cache_file = cache_file
        self.items: Dict[str, Item] = {}
        self.load()

    def load(self):
        """Charge les items depuis le fichier JSON vers des objets Item."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    self.items = {
                        code: Item.from_dict(d) for code, d in raw_data.items()
                    }
                print(f"📦 {len(self.items)} items chargés depuis le cache.")
            except Exception as e:
                print(f"⚠️ Erreur lors du chargement du cache : {e}")
        else:
            print("⚠️ Aucun cache d'items trouvé. Pensez à lancer update().")

    async def update(self):
        """Récupère TOUS les items de l'API et rafraîchit le cache."""
        print("🔄 Mise à jour de la base de données des items via l'API...")
        all_items_objects = {}
        page = 1

        while True:
            response = await self.client.get(
                "/items", params={"page": page, "size": 100}
            )
            if response.status_code != 200:
                break

            data = response.json()
            for item_data in data.get("data", []):
                all_items_objects[item_data["code"]] = Item.from_dict(item_data)

            total_pages = data.get("pages", 1)
            print(f"📥 Page {page}/{total_pages} récupérée...")

            if page >= total_pages:
                break
            page += 1

        self.items = all_items_objects
        self.save()
        print(f"✅ Base d'items mise à jour : {len(self.items)} objets enregistrés.")

    def save(self):
        """Sauvegarde les objets Item en JSON (en les convertissant en dict)."""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        dict_to_save = {code: item.to_dict() for code, item in self.items.items()}

        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(dict_to_save, f, indent=4)

    def get_by_code(self, code: str) -> Optional[Item]:
        return self.items.get(code)

    def search(
        self,
        name: str = None,
        min_level: int = 0,
        item_type: str = None,
        craft_skill: str = None,
    ) -> List[Item]:
        results = list(self.items.values())

        if name:
            results = [i for i in results if name.lower() in i.name.lower()]
        if min_level > 0:
            results = [i for i in results if i.level >= min_level]
        if item_type:
            results = [i for i in results if i.type == item_type]
        if craft_skill:
            results = [
                i for i in results if i.craft and i.craft.get("skill") == craft_skill
            ]

        return sorted(results, key=lambda i: i.level)

    def get_craftable_items(self, skill: str) -> List[Item]:
        return self.search(craft_skill=skill)
