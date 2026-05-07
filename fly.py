import os
import signal
import asyncio
from dotenv import load_dotenv
from models.account import Account
from routines import gathering, fighting, crafting

load_dotenv()

shutdown_event = asyncio.Event()


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print(f"\n🛑 Signal {sig} reçu. Arrêt du bot...")
    shutdown_event.set()


async def main():
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    account = Account(token=os.getenv("ARTIFACTS_TOKEN"))

    print("🚀 Initialisation du compte...")
    await account.initialize()

    hero_names = ["Kioyaa", "Kioyaa_g", "Kio_wood", "Kio_fish", "Kio_util"]
    heroes = [account.add_character(name) for name in hero_names]

    # crafting(heroes[0], "sticky_dagger", 9999) shrimp_spot
    heroes[0].default_task = lambda: gathering(heroes[0], "copper_rocks")
    heroes[1].default_task = lambda: gathering(heroes[1], "iron_rocks")
    heroes[2].default_task = lambda: gathering(heroes[2], "spruce_tree")
    heroes[3].default_task = lambda: gathering(heroes[3], "gudgeon_spot")
    heroes[4].default_task = lambda: gathering(heroes[4], "copper_rocks")

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
    except Exception as e:
        print(f"❌ Erreur: {e}")
        raise
