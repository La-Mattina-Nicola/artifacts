import asyncio
import json
import os


class WorldMap:
    def __init__(self, client, cache_file="data/map_cache.json"):
        self.client = client
        self.cache_file = cache_file
        self.tiles = {}
        self.banks = []
        self.monsters = {}
        self.resources = {}

    async def init_map(self, force_update=False):
        if not force_update and os.path.exists(self.cache_file):
            print(f"INFO: Chargement de la carte depuis le cache...")
            self._load_from_file()
        else:
            await self.update_map()

    async def update_map(self):
        page = 1
        self.tiles = {}
        print("🌍 Téléchargement de la carte (Layer: overworld)...")

        while True:
            # IMPORTANT: On précise le layer pour ne pas mélanger les maps
            response = await self.client.get(
                "/maps",
                params={
                    "page": page,
                    "size": 100,
                    "layer": "overworld",  # On se concentre sur la surface
                },
            )

            if response.status_code != 200:
                break

            data = response.json()
            maps_data = data.get("data", [])
            if not maps_data:
                break

            for tile in maps_data:
                # Clé unique basée sur les coordonnées
                pos_key = f"{tile['x']},{tile['y']}"
                self.tiles[pos_key] = tile

            if page >= data.get("pages", 1):
                break
            page += 1

        self._save_to_file()
        self._index_poi()
        print(
            f"✅ Carte prête. Banques: {len(self.banks)} | Ressources: {len(self.resources)}"
        )

    def _index_poi(self):
        self.banks = []
        self.monsters = {}
        self.resources = {}

        for pos_str, tile in self.tiles.items():
            coords = tuple(map(int, pos_str.split(",")))

            # Dans ton JSON, c'est interactions -> content
            interactions = tile.get("interactions")
            if not interactions:
                continue

            content = interactions.get("content")
            if not content:
                continue

            c_type = content.get("type")
            c_code = content.get("code")

            if c_type == "bank":
                self.banks.append(coords)
            elif c_type == "monster":
                if c_code not in self.monsters:
                    self.monsters[c_code] = []
                self.monsters[c_code].append(coords)
            elif c_type == "resource":
                if c_code not in self.resources:
                    self.resources[c_code] = []
                self.resources[c_code].append(coords)

    def _save_to_file(self):
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.tiles, f)

    def _load_from_file(self):
        with open(self.cache_file, "r", encoding="utf-8") as f:
            self.tiles = json.load(f)
        self._index_poi()

    def get_nearest_resource(self, start_pos, resource_code):
        spots = self.resources.get(resource_code, [])
        return self._find_nearest(start_pos, spots)

    def _find_nearest(self, start_pos, target_list):
        if not target_list:
            return None
        return min(
            target_list,
            key=lambda p: abs(start_pos[0] - p[0]) + abs(start_pos[1] - p[1]),
        )

    def get_nearest_bank(self, start_pos):
        """Trouve la banque la plus proche."""
        return self._find_nearest(start_pos, self.banks)

    def debug_tile(self, x, y):
        tile = self.tiles.get(f"{x},{y}")
        if tile:
            # Extraction propre pour le debug
            content = tile.get("interactions", {}).get("content")
            print(f"DEBUG TILE ({x},{y}): {tile.get('name')} | Contenu: {content}")
        else:
            print(f"DEBUG TILE ({x},{y}): Case absente (Mauvais layer ou hors limites)")
