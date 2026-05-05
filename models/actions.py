from abc import ABC
from typing import Dict


class BaseAction(ABC):
    def __init__(self, character):
        self.char = character


class MoveAction(BaseAction):
    async def to_coords(self, x, y):
        if int(self.char.x) == int(x) and int(self.char.y) == int(y):
            return True

        print(f"🏃 {self.char.name} se déplace vers ({x}, {y})...")
        response = await self.char.client.post(
            f"/my/{self.char.name}/action/move", {"x": int(x), "y": int(y)}
        )

        if response.status_code == 200:
            data = response.json()["data"]
            self.char.x = data["character"]["x"]
            self.char.y = data["character"]["y"]
            print(f"📍 {self.char.name} est arrivé en ({self.char.x}, {self.char.y})")
            return True
        else:
            error_details = response.json().get("error", "Erreur inconnue")
            print(f"⚠️ Échec ({response.status_code}): {error_details}")
            return False

    async def to_bank(self):
        """Trajet automatique vers la banque la plus proche."""
        target = self.char.world_map.get_nearest_bank((self.char.x, self.char.y))
        if target:
            return await self.to_coords(*target)
        return False


class FightAction(BaseAction):
    async def attack(self):
        """Lance un combat sur la case actuelle."""
        print(f"⚔️ {self.char.name} engage le combat...")
        response = await self.char.client.post(f"/my/{self.char.name}/action/fight")

        res_json = response.json()

        if response.status_code == 200:
            data = res_json.get("data", {})
            characters_list = data.get("characters", [])
            char_data = next(
                (c for c in characters_list if c.get("name") == self.char.name), None
            )

            new_hp = char_data.get("hp")

            if new_hp is not None:
                self.char.hp = new_hp
        if response.status_code == 200:
            data = res_json.get("data", {})
            fight_data = data.get("fight", {})
            result = fight_data.get("result")
            xp = fight_data.get("xp", 0)

            if result == "win":
                print(f"✅ Victoire ! XP gagnée : {xp}")
                drops = fight_data.get("drops", [])
                for drop in drops:
                    print(f"📦 Drop : {drop.get('quantity')}x {drop.get('code')}")
            else:
                print(f"💀 Combat terminé. Résultat : {result}")
            return True
        else:
            # Cas d'erreur (Cooldown, mort, etc.)
            err = res_json.get("error", {})
            print(f"❌ Erreur {err.get('code')}: {err.get('message')}")
            return False


class RestAction(BaseAction):
    async def rest(self):
        print(f"⚔️ {self.char.name} se repose ...")
        response = await self.char.client.post(f"/my/{self.char.name}/action/rest")

        res_json = response.json()

        if response.status_code == 200:
            data = res_json.get("data", {})
            cooldown_data = data.get("cooldown", {})
            char_data = data.get("character", {})
            self.char.hp = char_data.get("hp", self.char.hp)
            print(
                f"Repos terminé ! attente de {cooldown_data.get('remaining_seconds', {})}"
            )
            return True
        else:
            err = res_json.get("error", {})
            print(f"Erreur : {err.get('message')}")
            return False


class GatherAction(BaseAction):
    async def collect(self):
        """Exécute une tentative de récolte sur la case actuelle."""
        print(f"⛏️ {self.char.name} commence à récolter...")

        response = await self.char.client.post(f"/my/{self.char.name}/action/gathering")

        if response.status_code == 200:
            data = response.json()["data"]
            details = data.get("details", {})
            items_gained = details.get("items", [])

            for item in items_gained:
                print(f"  -> +{item['quantity']} {item['code']}")

            self.char.inventory = data.get("character", {}).get("inventory", [])
            self.char.client.cooldown_expiration = data.get("cooldown_expiration")
            return True

        elif response.status_code == 493:
            print("⚠️ La ressource n'est pas disponible sur cette case.")
        elif response.status_code == 497:
            print("🎒 Inventaire plein !")
        elif response.status_code == 498:
            print("❌ Outil manquant ou niveau de compétence trop faible.")

        return False
