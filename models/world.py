import json
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any


@dataclass
class MapContent:
    type: str
    code: str


@dataclass
class MapTile:
    x: int
    y: int
    name: str
    skin: str
    content: Optional[MapContent] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Hydrate une case à partir du JSON de l'API."""
        raw_content = data.get("interactions", {}).get("content")
        content_obj = None
        if raw_content:
            content_obj = MapContent(
                type=raw_content.get("type"), code=raw_content.get("code")
            )

        return cls(
            x=data["x"],
            y=data["y"],
            name=data["name"],
            skin=data["skin"],
            content=content_obj,
        )


class WorldMap:
    def __init__(self, client, cache_file="data/map_cache.json"):
        self.client = client
        self.cache_file = cache_file
        self.tiles: Dict[str, MapTile] = {}

        self.banks: List[Tuple[int, int]] = []
        self.monsters: Dict[str, List[Tuple[int, int]]] = {}
        self.resources: Dict[str, List[Tuple[int, int]]] = {}

    async def init_map(self, force_update=False):
        if not force_update and os.path.exists(self.cache_file):
            print("INFO: Chargement de la carte depuis le cache...")
            self._load_from_file()
        else:
            await self.update_map()

    async def update_map(self):
        page = 1
        all_raw_tiles = {}
        print("🌍 Téléchargement de la carte (Layer: overworld)...")

        while True:
            response = await self.client.get(
                "/maps",
                params={"page": page, "size": 100, "layer": "overworld"},
            )
            if response.status_code != 200:
                break

            data = response.json()
            maps_data = data.get("data", [])
            if not maps_data:
                break

            for tile_data in maps_data:
                pos_key = f"{tile_data['x']},{tile_data['y']}"
                all_raw_tiles[pos_key] = tile_data

            if page >= data.get("pages", 1):
                break
            page += 1

        self._save_to_file(all_raw_tiles)
        self.tiles = {k: MapTile.from_dict(v) for k, v in all_raw_tiles.items()}
        self._index_poi()
        print(f"✅ Carte prête. {len(self.tiles)} cases chargées.")

    def _index_poi(self):
        """Réinitialise et remplit les index de Points d'Intérêt."""
        self.banks = []
        self.monsters = {}
        self.resources = {}

        for tile in self.tiles.values():
            if not tile.content:
                continue

            coords = (tile.x, tile.y)
            c_type = tile.content.type
            c_code = tile.content.code

            if c_type == "bank":
                self.banks.append(coords)
            elif c_type == "monster":
                self.monsters.setdefault(c_code, []).append(coords)
            elif c_type == "resource":
                self.resources.setdefault(c_code, []).append(coords)

    def _save_to_file(self, data):
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _load_from_file(self):
        with open(self.cache_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            self.tiles = {k: MapTile.from_dict(v) for k, v in raw_data.items()}
        self._index_poi()

    def _find_nearest(
        self, start_pos: Tuple[int, int], target_list: List[Tuple[int, int]]
    ):
        if not target_list:
            return None

        return min(
            target_list,
            key=lambda p: abs(start_pos[0] - p[0]) + abs(start_pos[1] - p[1]),
        )

    def get_nearest_bank(self, start_pos):
        return self._find_nearest(start_pos, self.banks)

    def get_nearest_resource(self, resource_code: str, start_pos: Tuple[int, int]):
        """Trouve la coordonnée la plus proche pour un code de ressource donné."""
        target_list = self.resources.get(resource_code, [])

        if not target_list:
            return None

        return self._find_nearest(start_pos, target_list)

    def get_nearest_monster(self, monster_code: str, start_pos: tuple):
        """Trouve le monstre le plus proche pour un code donné."""
        target_list = self.monsters.get(monster_code, [])

        if not target_list:
            print(f"❓ {monster_code} introuvable sur la map (liste vide).")
            return None

        return self._find_nearest(start_pos, target_list)

    def get_tile(self, x, y) -> Optional[MapTile]:
        return self.tiles.get(f"{x},{y}")
