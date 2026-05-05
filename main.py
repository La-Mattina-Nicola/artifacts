import os
import asyncio
from dotenv import load_dotenv
from api.client import AsyncApiClient
from models.world import WorldMap
from models.character import Character

# Charge les variables du fichier .env
load_dotenv()


async def test():
    load_dotenv()
    client = AsyncApiClient(token=os.getenv("ARTIFACTS_TOKEN"))
    world = WorldMap(client)
    await world.init_map()

    my_hero = Character("Kioyaa", client, world)
    await my_hero.sync()

    # 1. Trouver le poulet le plus proche
    chicken_pos = world.monsters.get("chicken")
    if chicken_pos:
        target = world._find_nearest((my_hero.x, my_hero.y), chicken_pos)

        # 2. Se déplacer
        if await my_hero.mover.to_coords(*target):
            # 3. Combattre 3 fois
            for i in range(3):
                print(f"--- Tour de farm {i + 1}/3 ---")
                success = await my_hero.fighter.attack()
                print(f"DEBUG: Prochain CD prévu à {client.cooldown_expiration}")
                if not success:
                    break

    await client.close()


if __name__ == "__main__":
    asyncio.run(test())
