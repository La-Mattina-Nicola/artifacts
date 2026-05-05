from models.world import WorldMap
from models.character import Character


async def farm_monster(hero: Character, world: WorldMap, monster_id, iterations=0):
    """Routine de farm fighting"""
    monster_pos = world.monsters.get(monster_id)
    max_damage_seen = 0

    if not monster_pos:
        print(f"Impossible de trouver {monster_id} sur la carte")
        return

    target = world._find_nearest((hero.x, hero.y), monster_pos)

    cpt = 0
    while True:
        cpt += 1
        if cpt == iterations:
            break

        #if hero.inventory.

        if (hero.x, hero.y) != target:
            if not await hero.mover.to_coords(*target):
                print("Erreur déplacement")
                break

        hp_before = hero.hp
        success = await hero.attack()

        if success:
            damage_taken = hp_before - hero.hp
            max_damage_seen = max(damage_taken, max_damage_seen)
        else:
            print("Combat perdu / ou interrompu")
            break
