from models.character import Character
from .utils import cancellable


@cancellable
async def gathering(char: "Character", resource_code, quantity=1):
    await char.sync()

    def gathered_quantity():

        bank_quantity = char.account.bank.quantity(resource_code)
        actual_quantity = char.inventory_quantity(resource_code) + bank_quantity
        return actual_quantity

    while gathered_quantity() < quantity:
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

        # 2. Résolution du node_code
        current_pos = (char.x, char.y)

        pos = char.account.world.get_nearest_resource(resource_code, current_pos)

        if not pos:
            # Sinon, on le traite comme un item code → on cherche ses sources
            node_codes = char.account.resources.get_sources_for_item(resource_code)
            pos = char.account.world.get_nearest_resource(
                next(iter(node_codes)), current_pos
            )
            if not pos:
                print(f"❌ Aucune ressource trouvée pour '{resource_code}'.")
                char.default_task = None
                return

        if current_pos != pos:
            await char.move(*pos)
            continue

        # 4. Gather
        await char.gather()
        await char.sync()
