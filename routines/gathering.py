from models.character import Character
from .utils import cancellable


@cancellable
async def gathering(char: "Character", resource_code, quantity=1):
    await char.sync()

    def gathered_quantity():
        bank_quantity = char.account.bank.quantity(resource_code)
        return bank_quantity

    sources = char.account.resources.get_resource_objects_for_item(resource_code)
    if sources:
        skill = next(iter(sources)).skill
        if not char.is_equipped_with_best_tool_for_skill(skill):
            await char.equip_best_tool_for_skill(skill)

    while gathered_quantity() < quantity:
        await char.wait_until_ready()

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

        current_pos = (char.x, char.y)
        pos = char.account.world.get_nearest_resource(resource_code, current_pos)

        if not pos:
            node_codes = char.account.resources.get_sources_for_item(resource_code)

            if not node_codes:
                char.default_task = None
                return

            pos = None
            for node_code in node_codes:
                pos = char.account.world.get_nearest_resource(node_code, current_pos)

            if not pos:
                print(
                    f"❌ Aucun node trouvé pour les sources de '{resource_code}': {node_codes}"
                )
                char.default_task = None
                return

        if current_pos != pos:
            await char.move(*pos)
            continue

        await char.gather()
        await char.sync()
