import os
import asyncio
import signal
from contextlib import suppress
from dotenv import load_dotenv

from models.account import Account

from routines import gathering, fighting, crafting
from cli.commands import _make_task

load_dotenv()


async def main():
    hero_tasks = []

    print("🚀 Initialisation du bot (Mode Serveur/Fly.io)...")

    token = os.getenv("ARTIFACTS_TOKEN")
    if not token:
        print("❌ Erreur : ARTIFACTS_TOKEN non trouvé dans l'environnement.")
        return

    account = Account(token=token)
    await account.initialize()

    hero_tasks.append(asyncio.create_task(account.listen_completions()))

    default_tasks = {
        "Kioyaa": (fighting, ["mushmush"]),
        "Kioyaa_g": (fighting, ["wolf"]),
        "Kio_wood": (fighting, ["wolf"]),
        "Kio_fish": (fighting, ["green_slime"]),
        "Kio_util": (fighting, ["wolf"]),
    }

    for name, (routine, args) in default_tasks.items():
        char = account.add_character(name)
        await char.sync()

        char.default_task = _make_task(char, routine, *args)

        task = asyncio.create_task(char.main_loop())
        hero_tasks.append(task)
        print(f"✅ Héros {name} démarré.")

    print(f"🤖 Bot opérationnel avec {len(default_tasks)} héros.")

    try:
        await asyncio.gather(*hero_tasks)
    except asyncio.CancelledError:
        print("\n⚠️ Signal d'arrêt reçu...")
    finally:
        for t in hero_tasks:
            t.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.gather(*hero_tasks, return_exceptions=True)
        print("🛑 Bot arrêté proprement.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
