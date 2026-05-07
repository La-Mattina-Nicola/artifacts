import os
import asyncio
from dotenv import load_dotenv
from models.account import Account
from routines import gathering, fighting, crafting

load_dotenv()


async def main():
    account = Account(token=os.getenv("ARTIFACTS_TOKEN"))

    print("🚀 Initialisation du compte...")
    await account.initialize()

    hero_names = ["Kioyaa", "Kioyaa_g", "Kio_wood", "Kio_fish", "Kio_util"]
    heroes = [account.add_character(name) for name in hero_names]

    # crafting(heroes[0], "cooked_gudgeon", 9999) ash_tree
    heroes[0].default_task = lambda: gathering(heroes[0], "ash_tree")
    heroes[1].default_task = lambda: gathering(heroes[1], "iron_rocks")
    heroes[2].default_task = lambda: gathering(heroes[2], "copper_rocks")
    heroes[3].default_task = lambda: fighting(heroes[3], "sheep")
    heroes[4].default_task = lambda: fighting(heroes[4], "red_slime")

    loop_tasks = []
    for hero in heroes:
        await hero.sync()

        loop_tasks.append(asyncio.create_task(hero.main_loop()))

    # On laisse le bot tourner indéfiniment
    print(f"✅ {len(heroes)} héros sont en ligne !")
    await asyncio.gather(*loop_tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot arrêté par l'utilisateur.")
