import os
import asyncio
from dotenv import load_dotenv
from api.client import AsyncApiClient
from models.world import WorldMap
from models.character import Character, BankManager
from models.item_manager import ItemsManager

# Charge les variables du fichier .env
load_dotenv()


async def test():
    load_dotenv()
    client = AsyncApiClient(token=os.getenv("ARTIFACTS_TOKEN"))
    world = WorldMap(client)
    await world.init_map()

    my_hero = Character("Kioyaa", client, world)
    await my_hero.sync()

    # 1. Trouver le blue slime le plus proche
    green_slime_pos = world.monsters.get("green_slime")

    if green_slime_pos:
        target = world._find_nearest((my_hero.x, my_hero.y), green_slime_pos)
        if my_hero.hp != my_hero.max_hp:
            await my_hero.rest()
        # 2. Se déplacer
        if await my_hero.mover.to_coords(*target):
            # 3. Combattre 3 fois
            max_damage_seen = 0
            for i in range(3):
                if max_damage_seen > 0 and my_hero.hp <= (max_damage_seen + 5):
                    print(
                        f"⚖️ Risque de mort (HP: {my_hero.hp} <= Dégâts max: {max_damage_seen}). Repos..."
                    )
                    await my_hero.rest()
                hp_before = my_hero.hp
                print(f"--- Tour de farm {i + 1}/3 ---")
                success = await my_hero.attack()
                print(
                    f"DEBUG: Prochain CD prévu à {my_hero.client.cooldown_expiration}"
                )
                if success:
                    max_damage_seen = max(hp_before - my_hero.hp, max_damage_seen)
                    print(
                        f"📊 HP: {my_hero.hp}/{my_hero.max_hp} | Dégâts max enregistrés: {max_damage_seen}"
                    )
                else:
                    break

    await client.close()


async def items():

    load_dotenv()
    client = AsyncApiClient(token=os.getenv("ARTIFACTS_TOKEN"))
    world = WorldMap(client)
    await world.init_map()
    shared_bank = BankManager(client)
    await shared_bank.sync()

    items_db = ItemsManager(client)

    my_hero = Character("Kioyaa", client, shared_bank, items_db, world)
    await my_hero.sync()

    if not items_db.items:
        await items_db.update()

    sword = items_db.get_by_code("copper_dagger")
    if sword:
        print(f"Dégâts : {sword.effects}")
        print(f"Niveau requis : {sword.level}")

    code_test = "copper_dagger"
    mon_epee = items_db.get_by_code(code_test)

    if mon_epee and my_hero:
        if mon_epee.level <= my_hero.level:
            print(f"⚔️ {my_hero.name} peut équiper {mon_epee.name} !")
        else:
            print(f"❌ Niveau trop bas pour {mon_epee.name} (Requis: {mon_epee.level})")
    else:
        print(
            f"⚠️ Impossible de faire la vérification (Item {code_test} non trouvé ou Hero non synchro)"
        )

    copper_pos = world.get_nearest_resource((my_hero.x, my_hero.y), "copper_rocks")

    if copper_pos:
        print(f"Le cuivre le plus proche est en {copper_pos}")
        await my_hero.move(*copper_pos)


if __name__ == "__main__":
    #
    asyncio.run(items())
