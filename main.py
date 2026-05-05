import os
import asyncio
from dotenv import load_dotenv
from models.account import Account  # Importe ta nouvelle classe Account
from routines import gather_routine

load_dotenv()


async def main():
    # 1. Initialisation du compte (le cerveau central)
    # On lui passe le token, il s'occupe de créer le client, la banque, etc.
    account = Account(token=os.getenv("ARTIFACTS_TOKEN"))

    # 2. Chargement des données partagées (Items, Banque, Map)
    # C'est ici qu'on fait les appels API initiaux
    print("🚀 Initialisation du compte...")
    await account.initialize()

    # 3. Création des personnages
    # Ils reçoivent automatiquement l'accès à la banque et aux items via l'objet account
    hero_names = ["Kioyaa", "Kioyaa_g", "Kio_wood", "Kio_fish", "Kio_util"]
    heroes = [account.add_character(name) for name in hero_names]

    # Utilise bien "copper_rocks" pour la recherche sur la map
    heroes[0].default_task = lambda: gather_routine(heroes[0], "copper_rocks")
    heroes[1].default_task = lambda: gather_routine(heroes[1], "iron_rocks")
    heroes[2].default_task = lambda: gather_routine(heroes[2], "ash_tree")
    heroes[3].default_task = lambda: gather_routine(heroes[3], "gudgeon_spot")
    heroes[4].default_task = lambda: gather_routine(heroes[4], "sunflower_field")

    # 4. Premier Sync et démarrage des loops
    print("🔄 Synchronisation des personnages et démarrage des boucles...")

    # On prépare les tâches : sync() d'abord, puis main_loop()
    # On utilise asyncio.create_task pour qu'ils tournent tous en même temps
    loop_tasks = []
    for hero in heroes:
        await (
            hero.sync()
        )  # On les sync un par un au début pour avoir les stats fraîches

        # Optionnel : Définir une tâche par défaut ici si tu en as déjà
        # hero.default_task = ma_fonction_de_farm

        loop_tasks.append(asyncio.create_task(hero.main_loop()))

    # 5. On laisse le bot tourner indéfiniment
    print(f"✅ {len(heroes)} héros sont en ligne !")
    await asyncio.gather(*loop_tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot arrêté par l'utilisateur.")
