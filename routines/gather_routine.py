from models.character import Character


async def gather_routine(char: Character, resource_code):
    """
    Une itération de la routine de récolte.
    """

    # 1. Si l'inventaire est plein, on va à la banque
    # Dans gather_routine_2.py
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

    # 2. Trouver la ressource la plus proche (via ton world_map)
    pos = char.world_map.get_nearest_resource(resource_code, (char.x, char.y))
    if not pos:
        print(f"❓ {resource_code} introuvable sur la map.")
        return

    # 3. Aller à la ressource si on n'y est pas
    if (char.x, char.y) != pos:
        await char.mover.to_coords(*pos)
        return

    # 4. Récolter
    await char.gatherer.collect()  # [cite: 6, 7]
