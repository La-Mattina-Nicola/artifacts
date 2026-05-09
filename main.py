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
    # Ces listes/containers sont mutables : run_cli les reçoit vides,
    # puis init_task les remplit pendant que l'UI tourne déjà.
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

        hero_names = ["Kioyaa", "Kioyaa_g", "Kio_wood", "Kio_fish", "Kio_util"]
        new_heroes = [account.add_character(name) for name in hero_names]

        new_heroes[0].default_task = _make_task(
            lambda: gathering(new_heroes[0], "iron_rocks"), "⚒️ ", "copper_rocks"
        )
        new_heroes[1].default_task = _make_task(
            lambda: gathering(new_heroes[1], "iron_rocks"), "⚒️ ", "iron_rocks"
        )
        new_heroes[2].default_task = _make_task(
            lambda: gathering(new_heroes[2], "copper_rocks"), "⚒️ ", "copper_rocks"
        )
        new_heroes[3].default_task = _make_task(
            lambda: fighting(new_heroes[3], "red_slime"), "⚔️ ", "red_slime"
        )
        new_heroes[4].default_task = _make_task(
            lambda: fighting(new_heroes[4], "red_slime"), "⚔️ ", "red_slime"
        )

        # Sync puis démarre chaque héros
        for hero in new_heroes:
            await hero.sync()
            heroes.append(hero)  # UI le verra au prochain refresh
            hero_tasks.append(asyncio.create_task(hero.main_loop()))

        print(f"✅ {len(heroes)} héros sont en ligne !")

    init_task = asyncio.create_task(init_and_run())

    try:
        # L'UI démarre immédiatement ; stdout est redirigé dès maintenant
        await run_cli(
            heroes, ctx, world_map_key="world_map", items_manager_key="items_manager"
        )
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
