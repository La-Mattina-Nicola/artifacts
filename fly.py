import os
import asyncio
import signal
from contextlib import suppress
from dotenv import load_dotenv

from models.account import Account

# Importez vos modèles et routines normalement
from routines import gathering, fighting, crafting
from cli.commands import _make_task

load_dotenv()


async def main():
    # Liste pour suivre toutes les tâches asynchrones (boucles des héros)
    hero_tasks = []

    print("🚀 Initialisation du bot (Mode Serveur/Fly.io)...")

    # 1. Initialisation du compte
    token = os.getenv("ARTIFACTS_TOKEN")
    if not token:
        print("❌ Erreur : ARTIFACTS_TOKEN non trouvé dans l'environnement.")
        return

    account = Account(token=token)
    await account.initialize()

    # 2. Lancement de la tâche d'écoute des complétions (si nécessaire)
    hero_tasks.append(asyncio.create_task(account.listen_completions()))

    # 3. Configuration des tâches par défaut
    default_tasks = {
        "Kioyaa": (fighting, ["mushmush"]),
        "Kioyaa_g": (fighting, ["wolf"]),
        "Kio_wood": (fighting, ["wolf"]),
        "Kio_fish": (fighting, ["green_slime"]),
        "Kio_util": (fighting, ["wolf"]),
    }

    # 4. Initialisation des héros et démarrage de leurs boucles
    for name, (routine, args) in default_tasks.items():
        char = account.add_character(name)
        await char.sync()

        # Attribution de la tâche par défaut
        char.default_task = _make_task(char, routine, *args)

        # Lancement de la boucle principale du héros en arrière-plan
        task = asyncio.create_task(char.main_loop())
        hero_tasks.append(task)
        print(f"✅ Héros {name} démarré.")

    print(f"🤖 Bot opérationnel avec {len(default_tasks)} héros.")

    # 5. Garder le script en vie tant que les tâches tournent
    try:
        # On attend que toutes les tâches se terminent (ce qui n'arrive jamais sauf erreur ou arrêt)
        await asyncio.gather(*hero_tasks)
    except asyncio.CancelledError:
        print("\n⚠️ Signal d'arrêt reçu...")
    finally:
        # Nettoyage propre
        for t in hero_tasks:
            t.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.gather(*hero_tasks, return_exceptions=True)
        print("🛑 Bot arrêté proprement.")


if __name__ == "__main__":
    # Gestion propre du signal de fin pour Fly.io (SIGINT / SIGTERM)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
