from models.character import Character
from .utils import cancellable


@cancellable
async def fighting(char: Character, resource_code, treeshold: int = 150):
    """Routine de farm fighting"""
    await char.sync()
    # 1. Si l'inventaire est plein, on va à la banque
    if char.inventory_is_full(margin=1):
        print(f"🎒 {char.name} est plein. Go banque.")
        await char.mover.to_bank()

        # FILTRE : On ne prend que les objets qui ont un code et une quantité > 0
        items_to_deposit = [
            {"code": i["code"], "quantity": i["quantity"]}
            for i in char.inventory
            if i.get("code") and i.get("quantity", 0) > 0
        ]

        if items_to_deposit:
            await char.banker.deposit(items_to_deposit)
            await char.sync()
        return

    # 2. Trouver le monstre le plus proche
    pos = char.world_map.get_nearest_monster(resource_code, (char.x, char.y))
    if not pos:
        print(f"❓ {resource_code} introuvable sur la map.")
        return

    # 3. Aller à la ressource si on n'y est pas
    if (char.x, char.y) != pos:
        await char.mover.to_coords(*pos)
        return

    # 4. Se reposer si HP est bas
    if char.hp <= treeshold:
        await char.rest()
        # Après repos, re-sync pour voir le HP actuel
        await char.sync()
        # Si HP est toujours bas (repos échoué), ne pas attaquer
        if char.hp <= treeshold:
            print(f"⚠️ {char.name} a toujours HP bas ({char.hp}/{char.max_hp}), pause.")
            return

    # 5. Combattre
    await char.attack()
