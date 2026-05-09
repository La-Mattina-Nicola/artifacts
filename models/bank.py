from typing import Dict
from models.character import Character


class BankManager:
    def __init__(self, client):
        self.client = client
        self.content: Dict[str, int] = {}
        self.gold: int = 0

    async def sync(self):
        """Synchronise tout le contenu de la banque (Items + Gold)."""
        all_items = {}
        page = 1
        while True:
            res = await self.client.get(
                "/my/bank/items", params={"page": page, "size": 100}
            )
            if res.status_code != 200:
                break
            data = res.json()
            for item in data.get("data", []):
                all_items[item["code"]] = item["quantity"]
            if page >= data.get("pages", 1):
                break
            page += 1
        self.content = all_items

        res_gold = await self.client.get("/my/bank/gold")
        if res_gold.status_code == 200:
            self.gold = res_gold.json()["data"]["quantity"]
        print(f"🏦 Banque synchronisée : {len(self.content)} types d'items.")

    async def _execute_deposit(self, char: Character, items: list):
        endpoint = f"/my/{char.name}/action/bank/deposit/item"

        res = await char.client.post(endpoint, json=items)

        if res.status_code == 200:
            data = res.json().get("data", {})

            for item in items:
                print(f"📦 {char.name} a déposé {item['quantity']}x {item['code']}")
                self.content[item["code"]] = (
                    self.content.get(item["code"], 0) + item["quantity"]
                )

            self._update_char(char, data)
            return True
        else:
            print(f"❌ Erreur dépôt groupé {char.name} ({res.status_code}): {res.text}")
            return False

    async def _execute_withdraw(self, char, items: list):
        res = await char.client.post(
            f"/my/{char.name}/action/bank/withdraw/item", json=items
        )
        if res.status_code == 200:
            data = res.json().get("data", {})
            for item in items:
                code, qty = item["code"], item["quantity"]
                print(f"📦 {char.name} a pris {item['quantity']}x {item['code']}")
                if code in self.content:
                    self.content[code] -= qty
            self._update_char(char, data)
            return True
        else:
            err = res.json().get("error", {})
            error_code = err.get("code")
            error_msg = err.get("message", "Erreur inconnue")
            print(f"❌ Erreur retrait {char.name} ({error_code}): {error_msg}")
            return False

    def _update_char(self, char, data):
        # Chercher le bon character par son nom dans data.characters
        char_data = None
        if data.get("characters"):
            for c in data["characters"]:
                if c.get("name") == char.name:
                    char_data = c
                    break

        # Fallback: si pas trouvé, prendre le premier
        if not char_data and data.get("characters"):
            char_data = data["characters"][0]

        # Fallback: ancienne structure
        if not char_data:
            char_data = data.get("character")

        if char_data:
            char.inventory = char_data.get("inventory", char.inventory)
            char.gold = char_data.get("gold", char.gold)
            char.hp = char_data.get("hp", char.hp)
            char.level = char_data.get("level", char.level)

        # Cooldown depuis data.cooldown ou data.cooldown_expiration
        cooldown_data = data.get("cooldown", {})
        if cooldown_data.get("expiration"):
            char.cooldown_expiration = cooldown_data.get("expiration")
        elif data.get("cooldown_expiration"):
            char.cooldown_expiration = data.get("cooldown_expiration")
