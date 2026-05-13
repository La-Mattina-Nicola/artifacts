import json
import os
from collections import defaultdict
from typing import Dict, List, Set, Tuple


class ResourceData:
    """Modèle pour une ressource individuelle."""

    def __init__(self, data: dict):
        self.name = data["name"]
        self.code = data["code"]
        self.level = data.get("level", 1)
        self.skill = data.get("skill", "")
        # Drops: liste de dicts [{"code": "iron_ore", "rate": 10}, ...]
        self.drops = data.get("drops", [])


class ResourceManager:
    def __init__(self, client, cache_file="data/resources.json"):
        self.client = client
        self.cache_file = cache_file
        self.resources: Dict[str, ResourceData] = {}
        # Index inversé : quel item est looté par quelle ressource
        self._item_to_resources = defaultdict(set)

    async def init(self, force_update=False):
        """Initialise les ressources depuis le cache ou l'API."""
        print("🔄 Initialisation des ressources...")
        cache_exists = os.path.exists(self.cache_file)

        if not force_update and cache_exists:
            with open(self.cache_file, "r") as f:
                cached_data = json.load(f)

            # Vérification légère : on check le total via un HEAD ou une petite requête
            api_total = await self._fetch_total_count()

            if len(cached_data) == api_total:
                print(f"INFO: {api_total} ressources chargées depuis le cache.")
                self._build_from_data(cached_data)
                return

        # Si différence ou pas de cache, on télécharge tout
        print("🌍 Mise à jour des ressources depuis l'API...")
        all_data = await self._fetch_all_from_api()
        self._save_to_cache(all_data)
        self._build_from_data(all_data)

    async def _fetch_total_count(self) -> int:
        """Récupère le nombre total de ressources existantes sur l'API."""
        response = await self.client.get("/resources", params={"size": 1})
        if response.status_code == 200:
            return response.json().get("total", 0)
        return 0

    async def _fetch_all_from_api(self) -> List[dict]:
        """Pagination pour récupérer l'intégralité des ressources."""
        all_resources = []
        page = 1
        while True:
            resp = await self.client.get(
                "/resources", params={"page": page, "size": 100}
            )
            data = resp.json()
            all_resources.extend(data["data"])
            if page >= data["pages"]:
                break
            page += 1
        return all_resources

    def _build_from_data(self, data_list: List[dict]):
        """Peuple le dictionnaire et l'index inversé."""
        self.resources.clear()
        self._item_to_resources.clear()
        for d in data_list:
            res = ResourceData(d)
            self.resources[res.code] = res
            for drop in res.drops:
                self._item_to_resources[drop["code"]].add(res.code)

    def _save_to_cache(self, data: List[dict]):
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, "w") as f:
            json.dump(data, f)

    def get_resource_objects_for_item(self, item_code: str) -> List["ResourceData"]:
        codes = self._item_to_resources.get(item_code, set())
        return [self.resources[c] for c in codes if c in self.resources]

    def get_sources_for_item(self, item_code: str) -> Set[str]:
        """Retourne les codes des ressources qui drop cet item."""
        return self._item_to_resources.get(item_code, set())
