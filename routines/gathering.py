from models.character import Character
from .utils import cancellable
from utils.helper import resolve_to_node_code


@cancellable
async def gathering(char: "Character", resource_code, quantity=1):
    await char.sync()

    while quantity > 0:
        await char.wait_until_ready()
        # 1. Inventaire plein → banque
        if char.inventory_is_full(margin=0):
            print(f"🎒 {char.name} est plein. Go banque.")

            for _ in range(5):
                if await char.mover.to_bank():
                    break
                await char.sync()

            items_to_deposit = [
                {"code": i["code"], "quantity": i["quantity"]}
                for i in char.inventory
                if i.get("code") and i.get("quantity", 0) > 0
            ]

            if items_to_deposit:
                await char.banker.deposit(items_to_deposit)
                await char.sync()
            continue

        node_code = resolve_to_node_code(
            char.world_map, resource_code, char.account.items_db
        )

        if not node_code:
            print(f"❌ Impossible de résoudre {resource_code} en ressource de map.")
            return
        # 2. Trouver ressource
        pos = char.world_map.get_nearest_resource(node_code, (char.x, char.y))
        if not pos:
            print(f"❓ {resource_code} introuvable.")
            return

        # 3. Move si besoin
        if (char.x, char.y) != pos:
            await char.move(*pos)
            continue

        # 4. Gather
        ok = await char.gather()
        if ok:
            quantity -= 1
            await char.sync()
