from abc import ABC


class BaseAction(ABC):
    def __init__(self, character):
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

            # Chercher le bon character par son nom dans data.characters
            char_data = None
            if data.get("characters"):
                for c in data["characters"]:
                    if c.get("name") == self.char.name:
                        char_data = c
                        break

            # Fallback: si pas trouvé, prendre le premier
            if not char_data and data.get("characters"):
                char_data = data["characters"][0]

            if char_data:
                self.char.x = char_data.get("x", self.char.x)
                self.char.y = char_data.get("y", self.char.y)
                self.char.hp = char_data.get("hp", self.char.hp)
                self.char.level = char_data.get("level", self.char.level)
                self.char.gold = char_data.get("gold", self.char.gold)
            else:
                # Si pas de data.characters, mettre à jour les coords directement
                self.char.x = int(x)
                self.char.y = int(y)

            # # Logs détaillés
            # if (old_x, old_y) != (self.char.x, self.char.y):
            #     print(f"Position: ({old_x}, {old_y}) → ({self.char.x}, {self.char.y})")
            # if old_hp != self.char.hp:
            #     print(f"HP: {old_hp} → {self.char.hp}")
            # if old_gold != self.char.gold:
            #     print(f"Gold: {old_gold} → {self.char.gold}")

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
            char_data = None
            characters = data.get("characters", [])
            if characters:
                for c in characters:
                    if c.get("name") == self.char.name:
                        char_data = c
                        break
                # Fallback: si pas trouvé, prendre le premier
                if not char_data:
                    char_data = characters[0]

            if char_data:
                old_hp = self.char.hp
                old_level = self.char.level
                old_gold = self.char.gold

                self.char.hp = char_data.get("hp", self.char.hp)
                self.char.level = char_data.get("level", self.char.level)
                self.char.gold = char_data.get("gold", self.char.gold)
                self.char.inventory = char_data.get("inventory", self.char.inventory)

                # # Logs détaillés
                # if old_hp != self.char.hp:
                #     print(f"HP: {old_hp} → {self.char.hp}")
                # if old_level != self.char.level:
                #     print(f"Level: {old_level} → {self.char.level}")
                # if old_gold != self.char.gold:
                #     print(f"Gold: {old_gold} → {self.char.gold}")

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

            # Chercher le bon character par son nom dans data.characters
            char_data = None
            characters = data.get("characters", [])
            if characters:
                for c in characters:
                    if c.get("name") == self.char.name:
                        char_data = c
                        break
                # Fallback: si pas trouvé, prendre le premier
                if not char_data:
                    char_data = characters[0]

            if char_data:
                old_hp = self.char.hp
                old_gold = self.char.gold
                old_level = self.char.level

                self.char.hp = char_data.get("hp", self.char.hp)
                self.char.gold = char_data.get("gold", self.char.gold)
                self.char.level = char_data.get("level", self.char.level)

                # # Logs détaillés
                # if old_hp != self.char.hp:
                #     print(f"HP: {old_hp} → {self.char.hp}")
                # if old_gold != self.char.gold:
                #     print(f"Gold: {old_gold} → {self.char.gold}")
                # if old_level != self.char.level:
                #     print(f"Level: {old_level} → {self.char.level}")

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
                str = " | ".join(f"{item['code']} x{item['quantity']}" for item in loot)
                print(f"📦 {self.char.name:10}  - {str}")

            # Chercher le bon character par son nom dans data.characters
            char_data = None
            characters = data.get("characters", [])
            if characters:
                for c in characters:
                    if c.get("name") == self.char.name:
                        char_data = c
                        break
                # Fallback: si pas trouvé, prendre le premier
                if not char_data:
                    char_data = characters[0]

            if char_data:
                old_inventory = (
                    self.char.inventory.copy() if self.char.inventory else []
                )
                old_inv_total = sum(
                    item.get("quantity", 0)
                    for item in old_inventory
                    if item.get("code")
                )

                self.char.inventory = char_data.get("inventory", self.char.inventory)
                new_inv_total = sum(
                    item.get("quantity", 0)
                    for item in self.char.inventory
                    if item.get("code")
                )

                old_hp = self.char.hp
                self.char.hp = char_data.get("hp", self.char.hp)
                old_gold = self.char.gold
                self.char.gold = char_data.get("gold", self.char.gold)
                old_level = self.char.level
                self.char.level = char_data.get("level", self.char.level)

                # # Logs détaillés de la mise à jour
                # if old_inv_total != new_inv_total:
                #     print(f"Inventaire: {old_inv_total} items → {new_inv_total} items ({self.char.inventory_max_items} max)")
                # if old_hp != self.char.hp:
                #     print(f"HP: {old_hp} → {self.char.hp}")
                # if old_gold != self.char.gold:
                #     print(f"Gold: {old_gold} → {self.char.gold}")
                # if old_level != self.char.level:
                #     print(f"Level: {old_level} → {self.char.level}")

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

            # Mise à jour du personnage
            char_data = data.get("character")
            if char_data:
                self.char.hp = char_data.get("hp", self.char.hp)
                self.char.gold = char_data.get("gold", self.char.gold)
                self.char.level = char_data.get("level", self.char.level)
                self.char.inventory = char_data.get("inventory", self.char.inventory)

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
