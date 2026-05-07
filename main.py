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

    # crafting(heroes[0], "sticky_dagger", 9999) shrimp_spot
    heroes[0].default_task = lambda: gathering(heroes[0], "copper_rocks")
    heroes[1].default_task = lambda: crafting(heroes[1], "iron_bar", 999)
    heroes[2].default_task = lambda: fighting(heroes[2], "sheep")
    heroes[3].default_task = lambda: fighting(heroes[3], "yellow_slime")
    heroes[4].default_task = lambda: fighting(heroes[4], "yellow_slime")

    loop_tasks = []
    for hero in heroes:
        await hero.sync()

        loop_tasks.append(asyncio.create_task(hero.main_loop()))

    print(f"✅ {len(heroes)} héros sont en ligne !")
    await asyncio.gather(*loop_tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot arrêté par l'utilisateur.")
