import httpx
from functools import wraps


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


def auto_cooldown(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if self.character:
            await self.character.wait_until_ready()
        response = await func(self, *args, **kwargs)
        if not self.character:
            return response
        try:
            json_data = response.json()
            if response.status_code == 200:
                data = json_data.get("data", {})
                cooldown_exp = (
                    data.get("cooldown", {}).get("expiration")
                    or (
                        data.get("characters", [{}])[0].get("cooldown_expiration")
                        if data.get("characters")
                        else None
                    )
                    or find_key(json_data, "cooldown_expiration")
                )
                if cooldown_exp:
                    self.character.cooldown_expiration = cooldown_exp
        except Exception:
            pass
        return response
    return wrapper


class AsyncApiClient:
    def __init__(
        self, token: str, character=None, base_url: str = "https://api.artifactsmmo.com"
    ):
        self.token = token
        self.character = character
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
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
