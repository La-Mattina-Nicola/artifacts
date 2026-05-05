class MoveAction:
    def __init__(self, character):
        self.char = character

    async def to_coords(self, x, y):
        # Vérification immédiate pour éviter l'appel API inutile
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
            # ON AJOUTE CECI POUR COMPRENDRE :
            error_details = response.json().get("error", "Erreur inconnue")
            print(f"⚠️ Échec ({response.status_code}): {error_details}")
            return False

    async def to_bank(self):
        """Trajet automatique vers la banque la plus proche."""
        target = self.char.world_map.get_nearest_bank((self.char.x, self.char.y))
        if target:
            return await self.to_coords(*target)
        return False


class FightAction:
    def __init__(self, character):
        self.char = character

    async def attack(self):
        """Lance un combat sur la case actuelle."""
        print(f"⚔️ {self.char.name} engage le combat...")
        response = await self.char.client.post(f"/my/{self.char.name}/action/fight")

        # On récupère le JSON complet
        res_json = response.json()

        if response.status_code == 200:
            # Structure : {"data": {"fight": {"xp": 50, "result": "win" ...}, "character": {...}}}
            data = res_json.get("data", {})
            fight_data = data.get("fight", {})

            result = fight_data.get("result")
            xp = fight_data.get("xp", 0)  # 0 par défaut si pas d'xp

            if result == "win":
                print(f"✅ Victoire ! XP gagnée : {xp}")
                # Log des drops s'il y en a
                drops = fight_data.get("drops", [])
                for drop in drops:
                    print(f"📦 Drop : {drop.get('quantity')}x {drop.get('code')}")
            else:
                print(f"💀 Combat terminé. Résultat : {result}")

            # Mise à jour HP du perso
            char_info = data.get("character", {})
            self.char.hp = char_info.get("hp", self.char.hp)
            return True
        else:
            # Cas d'erreur (Cooldown, mort, etc.)
            err = res_json.get("error", {})
            print(f"❌ Erreur {err.get('code')}: {err.get('message')}")
            return False
