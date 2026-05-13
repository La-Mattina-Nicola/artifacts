import json
import os
from typing import Dict, List, Optional

from models.character import Character
from models.items import Item


class ItemsManager:
    def __init__(self, client, cache_file="data/items.json"):
        self.client = client
        self.cache_file = cache_file
        self.items: Dict[str, Item] = {}
        self.load()

    # ------------------------------------------------------------------
    # Chargement / sauvegarde
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """
        Charge les items depuis le cache JSON.
        Retourne True si le cache existait et a été chargé, False sinon.
        """
        if not os.path.exists(self.cache_file):
            print("⚠️  Aucun cache d'items trouvé.")
            return False

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            self.items = {code: Item.from_dict(d) for code, d in raw_data.items()}
            print(f"📦 {len(self.items)} items chargés depuis le cache.")
            return True
        except Exception as e:
            print(f"⚠️  Erreur lors du chargement du cache : {e}")
            return False

    def save(self):
        """Sauvegarde tous les items en JSON (données complètes)."""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(
                {code: item.to_dict() for code, item in self.items.items()},
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"💾 Cache sauvegardé : {len(self.items)} items → {self.cache_file}")

    # ------------------------------------------------------------------
    # Mise à jour depuis l'API
    # ------------------------------------------------------------------

    async def update(self):
        """
        Récupère TOUS les items de l'API page par page et rafraîchit le cache.
        À appeler explicitement quand une mise à jour est nécessaire.
        """
        print("🔄 Mise à jour de la base de données des items via l'API...")
        fetched: Dict[str, Item] = {}
        page = 1

        while True:
            response = await self.client.get(
                "/items", params={"page": page, "size": 100}
            )
            if response.status_code != 200:
                print(f"❌ Erreur HTTP {response.status_code} à la page {page}")
                break

            data = response.json()
            for item_data in data.get("data", []):
                fetched[item_data["code"]] = Item.from_dict(item_data)

            total_pages = data.get("pages", 1)
            print(f"  📥 Page {page}/{total_pages} — {len(data.get('data', []))} items")

            if page >= total_pages:
                break
            page += 1

        self.items = fetched
        self.save()
        print(f"✅ Base d'items mise à jour : {len(self.items)} items enregistrés.")

    async def load_or_update(self):
        """
        Charge le cache s'il existe, sinon lance une mise à jour API.
        C'est la méthode à appeler dans Account.initialize() pour éviter
        les appels API inutiles.
        """
        print("init items manager...")
        if not self.load():
            await self.update()

    # ------------------------------------------------------------------
    # Recherche
    # ------------------------------------------------------------------

    def get_by_code(self, code: str) -> Optional[Item]:
        return self.items.get(code)

    def search(
        self,
        name: str = None,
        min_level: int = 0,
        max_level: int = None,
        item_type: str = None,
        subtype: str = None,
        craft_skill: str = None,
        tradeable: bool = None,
    ) -> List[Item]:
        results = list(self.items.values())

        if name:
            results = [i for i in results if name.lower() in i.name.lower()]
        if min_level > 0:
            results = [i for i in results if i.level >= min_level]
        if max_level is not None:
            results = [i for i in results if i.level <= max_level]
        if item_type:
            results = [i for i in results if i.type == item_type]
        if subtype:
            results = [i for i in results if i.subtype == subtype]
        if craft_skill:
            results = [i for i in results if i.craft_skill == craft_skill]
        if tradeable is not None:
            results = [i for i in results if i.tradeable == tradeable]

        return sorted(results, key=lambda i: i.level)

    def get_craftable_items(self, skill: str) -> List[Item]:
        """Tous les items craftables avec un skill donné, triés par level."""
        return self.search(craft_skill=skill)

    def get_ingredients_for(self, item_code: str) -> List[Item]:
        """
        Retourne les objets Item correspondant aux ingrédients de craft,
        avec la quantité nécessaire injectée dans item.quantity.
        """
        item = self.get_by_code(item_code)
        if not item or not item.is_craftable:
            return []

        result = []
        for ingredient in item.craft_ingredients:
            ing = self.get_by_code(ingredient["code"])
            if ing:
                # On crée une copie légère avec la quantité requise
                import dataclasses

                ing_with_qty = dataclasses.replace(ing, quantity=ingredient["quantity"])
                result.append(ing_with_qty)
        return result

    def get_tools_for_skill(self, skill: str) -> List[Item]:
        return sorted(
            [
                item
                for item in self.items.values()
                if item.subtype == "tool"
                and any(e.get("code") == skill for e in item.effects)
            ],
            key=lambda i: i.level,
        )

    def get_best_tool_for_skill(self, skill: str, char: "Character") -> Optional[Item]:
        item_catalog = char.account.items_db.items  # Dict[str, Item]

        viable_tools = [
            item
            for code, qty in char.account.bank.content.items()
            if qty > 0
            and (item := item_catalog.get(code)) is not None
            and item.subtype == "tool"
            and any(e.get("code") == skill for e in item.effects)
            and item.level <= char.get_skill_level(skill)
        ]

        viable_tools.sort(key=lambda item: item.level)
        return viable_tools[-1] if viable_tools else None
