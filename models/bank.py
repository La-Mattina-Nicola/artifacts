from typing import Dict
from models.character import Character


class BankManager:
    def __init__(self, client):
        self.client = client
        self.content: Dict[str, int] = {}
        self.items_data: Dict[str, dict] = {}  # code → full item dict
        self.gold: int = 0

    async def sync(self):
        """Synchronise tout le contenu de la banque (Items + Gold)."""

        print("init bank...")
        all_items = {}
        all_items_data = {}
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
                all_items_data[item["code"]] = item  # store full dict
            if page >= data.get("pages", 1):
                break
            page += 1
        self.content = all_items
        self.items_data = all_items_data

        res_gold = await self.client.get("/my/bank/gold")
        if res_gold.status_code == 200:
            self.gold = res_gold.json()["data"]["quantity"]
        print(f"🏦 chronisée : {len(self.content)} types d'items.")

    async def _execute_deposit(self, char: Character, items: list):
        endpoint = f"/my/{char.name}/action/bank/deposit/item"

        res = await char.client.post(endpoint, json=items)

        if res.status_code == 200:
            await char.account.bank.sync()
            data = res.json().get("data", {})
            char.update_from_api(data.get("character", {}))

            for item in items:
                print(f"📦 {char.name} a déposé {item['quantity']}x {item['code']}")
                self.content[item["code"]] = (
                    self.content.get(item["code"], 0) + item["quantity"]
                )

            char.update_from_api(data.get("character", {}))
            await char.account.bank.sync()
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
            char.update_from_api(data.get("character", {}))
            await char.account.bank.sync()
            for item in items:
                code, qty = item["code"], item["quantity"]
                print(f"📦 {char.name} a pris {item['quantity']}x {item['code']}")
                if code in self.content:
                    self.content[code] -= qty
            return True
        else:
            err = res.json().get("error", {})
            error_code = err.get("code")
            error_msg = err.get("message", "Erreur inconnue")
            print(f"❌ Erreur retrait {char.name} ({error_code}): {error_msg}")
            return False

    def enough_in_bank(self, item_code: str, quantity: int) -> bool:
        """Vérifie si la banque contient au moins `quantity` de `item_code`."""
        value_in_bank = self.content.get(item_code, 0)
        return value_in_bank >= quantity

    def quantity(self, item_code: str) -> int:
        """Retourne la quantité de `item_code` présente dans la banque."""
        return self.content.get(item_code, 0)
