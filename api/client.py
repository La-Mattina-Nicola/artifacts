import asyncio
import httpx
from functools import wraps
from datetime import datetime, timezone


import asyncio
from datetime import datetime, timezone
from functools import wraps


def auto_cooldown(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):

        if hasattr(self, "cooldown_expiration") and self.cooldown_expiration:
            exp_str = self.cooldown_expiration.replace("Z", "+00:00")
            expire_at = datetime.fromisoformat(exp_str)
            now = datetime.now(timezone.utc)

            wait_time = (expire_at - now).total_seconds()
            if wait_time > 0:
                print(f"⏳ Attente forcée : {wait_time + 0.5:.2f}s...")
                await asyncio.sleep(wait_time + 0.5)

        response = await func(self, *args, **kwargs)

        if response.status_code == 200:
            json_data = response.json()

            def find_key(obj, key):
                """Cherche une clé dans un dictionnaire ou une liste imbriquée."""
                if isinstance(obj, dict):
                    if key in obj:
                        return obj[key]
                    for v in obj.values():
                        result = find_key(v, key)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_key(item, key)
                        if result:
                            return result
                return None

            new_exp = find_key(json_data, "cooldown_expiration")

            if new_exp:
                self.cooldown_expiration = new_exp
            else:
                print(f"DEBUG COMPLET : {json_data}")

        return response

    return wrapper


class AsyncApiClient:
    def __init__(self, token: str, base_url: str = "https://api.artifactsmmo.com"):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.client = httpx.AsyncClient(headers=self.headers, base_url=base_url)

    async def close(self):
        """À appeler à la fin du programme pour fermer les connexions."""
        await self.client.aclose()

    @auto_cooldown
    async def get(self, endpoint: str, params: dict = None):
        return await self.client.get(endpoint, params=params)

    @auto_cooldown
    async def post(self, endpoint: str, json: dict = None):
        return await self.client.post(endpoint, json=json)
