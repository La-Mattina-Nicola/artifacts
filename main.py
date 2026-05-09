import os
import asyncio
from contextlib import suppress
from dotenv import load_dotenv

from models.account import Account
from models import ItemsManager
from models import WorldMap
from routines import gathering, fighting, crafting

from cli.interface import run_cli
from cli.commands import _make_task

load_dotenv()


async def main():
    heroes = []
    ctx = {"items_manager": None, "world_map": None}
    hero_tasks = []

    async def init_and_run():
        """Init complète en arrière-plan, les print() vont dans les logs UI."""
        print("🚀 Initialisation du compte...")

        account = Account(token=os.getenv("ARTIFACTS_TOKEN"))
        await account.initialize()

        ctx["items_manager"] = ItemsManager(account.client)
        ctx["world_map"] = WorldMap(account.client)
        await ctx["world_map"].init_map()

        default_tasks = {
            "Kioyaa": (fighting, ["cow"]),
            "Kioyaa_g": (fighting, ["chicken"]),
            "Kio_wood": (fighting, ["green_slime"]),
            "Kio_fish": (fighting, ["cow"]),
            "Kio_util": (fighting, ["blue_slime"]),
        }

        for key, value in default_tasks.items():
            char = account.add_character(key)
            heroes.append(char)
            await char.sync()
            char.default_task = _make_task(char, value[0], *value[1])

            hero_tasks.append(asyncio.create_task(char.main_loop()))

    print(f"✅ {len(heroes)} héros sont en ligne !")
    init_task = asyncio.create_task(init_and_run())

    try:
        # L'UI démarre immédiatement ; stdout est redirigé dès maintenant
        await run_cli(
            heroes, ctx, world_map_key="world_map", items_manager_key="items_manager"
        )
    except Exception as e:
        print(str(e))
    finally:
        init_task.cancel()
        for t in hero_tasks:
            t.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.gather(init_task, *hero_tasks, return_exceptions=True)
        print("\n🛑 Bot arrêté.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
