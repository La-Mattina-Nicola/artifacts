from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.character import Character


class BaseAction(ABC):
    char: "Character"

    def __init__(self, character: "Character"):
        self.char = character


class MoveAction(BaseAction):
    async def to_coords(self, x, y):
        if int(self.char.x) == int(x) and int(self.char.y) == int(y):
            return True

        response = await self.char.client.post(
            f"/my/{self.char.name}/action/move", {"x": int(x), "y": int(y)}
        )

        res_json = response.json()

        if response.status_code == 200:
            data = res_json.get("data", {})
            self.char.update_from_api(data["character"])
            return True
        else:
            error_code = res_json.get("error", {}).get("code")
            error_details = res_json.get("error", "Erreur inconnue")
            print(f"⚠️ Échec ({response.status_code}): {error_details}")

            # Gestion spéciale de l'erreur 490 (already at destination)
            if error_code == 490:
                self.char.x = int(x)
                self.char.y = int(y)
                print(
                    f"📍 {self.char.name} est déjà arrivé en ({self.char.x}, {self.char.y})"
                )
                return True

            if error_code == 499:
                await self.char.sync()

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
        response = await self.char.client.post(f"/my/{self.char.name}/action/fight")
        res_json = response.json()

        if response.status_code == 200:
            data = res_json.get("data", {})

            # Chercher le bon character par son nom dans data.characters
            characters = data.get("characters", [])
            if characters:
                for c in data.get("characters", []):
                    if c["name"] == self.char.name:
                        self.char.update_from_api(c)

            # Gestion du résultat du combat
            fight_data = data.get("fight", {})
            result = fight_data.get("result")

            # L'XP et les drops sont dans fight.characters[0]
            fight_characters = fight_data.get("characters", [])
            xp = 0
            drops = []
            if fight_characters:
                char_fight_data = fight_characters[0]
                xp = char_fight_data.get("xp", 0)
                drops = char_fight_data.get("drops", [])

            if result == "win":
                print(f"✅ Victoire ! XP gagnée : {xp}")
                if drops:
                    str = " | ".join(
                        f"{item['code']} x{item['quantity']}" for item in drops
                    )
                    print(f"📦 {self.char.name:10} - {str}")
            else:
                print(f"💀 Combat terminé. Résultat : {result}")

            return True
        else:
            err = res_json.get("error", {})
            error_code = err.get("code")
            print(f"❌ Erreur {error_code}: {err.get('message')}")

            if error_code == 499:
                await self.char.sync()

            return False


class RestAction(BaseAction):
    async def rest(self):
        response = await self.char.client.post(f"/my/{self.char.name}/action/rest")

        res_json = response.json()

        if response.status_code == 200:
            data = res_json.get("data", {})
            cooldown_data = data.get("cooldown", {})
            remaining = cooldown_data.get("remaining_seconds", 0)

            self.char.update_from_api(data["character"])

            print(f"✅ Repos terminé ! Attente de {remaining}s avant prochain cooldown")
            return True
        else:
            err = res_json.get("error", {})
            error_code = err.get("code")
            print(f"❌ Erreur {error_code}: {err.get('message')}")

            if error_code == 499:
                await self.char.sync()

            return False


class GatherAction(BaseAction):
    async def collect(self):
        """Exécute une tentative de récolte sur la case actuelle."""

        response = await self.char.client.post(f"/my/{self.char.name}/action/gathering")

        if isinstance(response, bool):
            return response

        res_json = response.json()

        if response.status_code == 200:
            data = res_json.get("data", {})

            details_data = data.get("details", {})
            loot = details_data.get("items", [])
            if loot:
                str = " | ".join(f"x{item['quantity']} {item['code']}" for item in loot)
                print(f"📦 {self.char.name:7} - {str}")

            self.char.update_from_api(data["character"])
            return True

        else:
            error_code = res_json.get("error", {}).get("code")
            error_msg = res_json.get("error", {}).get("message", "Erreur inconnue")

            if error_code == 493:
                print("⚠️ La ressource n'est pas disponible sur cette case.")
            elif error_code == 497:
                inv_total = sum(
                    item.get("quantity", 0)
                    for item in self.char.inventory
                    if item.get("code")
                )
                print(
                    f"🎒 Inventaire plein ! ({inv_total}/{self.char.inventory_max_items} items)"
                )
                # Sync pour mettre à jour l'état réel
                await self.char.sync()
            elif error_code == 498:
                print("❌ Outil manquant ou niveau de compétence trop faible.")
            elif error_code == 499:
                print(f"⏱️ Cooldown: {error_msg}")
                await self.char.sync()
            else:
                print(f"Erreur {error_code}: {error_msg}")

        return False


class CraftAction(BaseAction):
    async def craft(self, item_code: str, quantity: int = 1) -> bool:
        """Craft `quantity` fois l'item `item_code` sur la case actuelle."""
        response = await self.char.client.post(
            f"/my/{self.char.name}/action/crafting",
            {"code": item_code, "quantity": quantity},
        )
        res_json = response.json()

        if response.status_code == 200:
            data = res_json.get("data", {})

            details = data.get("details", {})
            xp = details.get("xp", 0)
            items_crafted = details.get("items", [])

            if items_crafted:
                items_str = " | ".join(
                    f"{i['code']} x{i['quantity']}" for i in items_crafted
                )
                print(f"🔨 {self.char.name:10} - Crafté : {items_str} (+{xp} XP)")

            self.char.update_from_api(data["character"])

            return True

        else:
            err = res_json.get("error", {})
            error_code = err.get("code")
            msg = err.get("message", "Erreur inconnue")

            if error_code == 478:
                print(
                    f"❌ {self.char.name} — Matériaux manquants pour crafter {item_code}."
                )
            elif error_code == 493:
                print(
                    f"❌ {self.char.name} — Niveau de skill trop bas pour {item_code}."
                )
            elif error_code == 598:
                print(f"❌ {self.char.name} — Pas de workshop sur cette case.")
            elif error_code == 497:
                print(f"❌ {self.char.name} — Inventaire plein, impossible de crafter.")
            elif error_code == 499:
                await self.char.sync()
            else:
                print(f"❌ Erreur {error_code}: {msg}")

            return False
