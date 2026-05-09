from models.character import Character
from .utils import cancellable


@cancellable
async def gathering(char: Character, resource_code):
    """
    Une itération de la routine de récolte.
    """

    await char.sync()
    # 1. Si l'inventaire est plein, on va à la banque et on dépose
    if char.inventory_is_full(margin=0):
        print(f"🎒 {char.name} est plein. Go banque.")

        # Aller à la banque jusqu'à y arriver
        max_attempts = 5
        for attempt in range(max_attempts):
            success = await char.mover.to_bank()
            if success:
                break
            await char.sync()
        else:
            # Si échec après max_attempts, re-sync et quitter
            print(f"❌ {char.name} ne peut pas aller à la banque.")
            return

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

    # 2. Trouver la ressource la plus proche (via ton world_map)
    pos = char.world_map.get_nearest_resource(resource_code, (char.x, char.y))
    if not pos:
        print(f"❓ {resource_code} introuvable sur la map.")
        return

    # 3. Aller à la ressource si on n'y est pas
    if (char.x, char.y) != pos:
        await char.move(*pos)
        return

    # 4. Récolter
    await char.gather()
