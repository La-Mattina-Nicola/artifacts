from typing import Dict


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

    # Version optimisée : Un seul appel pour tout le sac
    async def _execute_deposit(self, char, items: list):
        endpoint = f"/my/{char.name}/action/bank/deposit/item"
        res = await char.client.post(endpoint, json=items)

        if res.status_code == 200:
            data = res.json().get("data", {})
            # On vérifie si 'character' existe avant de l'utiliser
            char_data = data.get("character")

            for item in items:
                print(f"📦 {char.name} a déposé {item['quantity']}x {item['code']}")
                self.content[item["code"]] = (
                    self.content.get(item["code"], 0) + item["quantity"]
                )

            if char_data:
                self._update_char(char, char_data)
            return True
        else:
            print(f"❌ Erreur dépôt groupé {char.name} ({res.status_code}): {res.text}")
            return False

    async def _execute_withdraw(self, char, items: list):
        res = await self.client.post(
            f"/my/{char.name}/action/bank/withdraw/item", json=items
        )
        if res.status_code == 200:
            for item in items:
                code, qty = item["code"], item["quantity"]
                if code in self.content:
                    self.content[code] -= qty
            self._update_char(char, res.json()["data"])
            return True
        return False

    def _update_char(self, char, data):
        char.inventory = data["character"]["inventory"]
        char.gold = data["character"]["gold"]
        char.client.cooldown_expiration = data["cooldown_expiration"]
