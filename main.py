import os
import asyncio
from dotenv import load_dotenv
from models.account import Account  # Importe ta nouvelle classe Account
from routines import gathering, fighting

load_dotenv()


async def main():
    account = Account(token=os.getenv("ARTIFACTS_TOKEN"))

    print("🚀 Initialisation du compte...")
    await account.initialize()

    hero_names = ["Kioyaa", "Kioyaa_g", "Kio_wood", "Kio_fish", "Kio_util"]
    heroes = [account.add_character(name) for name in hero_names]

    heroes[0].default_task = lambda: fighting(heroes[0], "green_slime")
    heroes[1].default_task = lambda: gathering(heroes[1], "ash_tree")
    heroes[2].default_task = lambda: gathering(heroes[2], "ash_tree")
    heroes[3].default_task = lambda: gathering(heroes[3], "ash_tree")
    heroes[4].default_task = lambda: gathering(heroes[4], "ash_tree")

    # On prépare les tâches : sync() d'abord, puis main_loop()
    # On utilise asyncio.create_task pour qu'ils tournent tous en même temps
    loop_tasks = []
    for hero in heroes:
        await hero.sync()

        loop_tasks.append(asyncio.create_task(hero.main_loop()))

    # 5. On laisse le bot tourner indéfiniment
    print(f"✅ {len(heroes)} héros sont en ligne !")
    await asyncio.gather(*loop_tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot arrêté par l'utilisateur.")
