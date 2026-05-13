from models import Character
from routines.fighting import fighting
from .utils import cancellable
import asyncio

task_items = (4, 13)
task_fight = (1, 2)


@cancellable
async def tasking(char: "Character", type="items"):
    await char.sync()
    await char.account.bank.sync()
    
    if char.task_type != "":
        type = char.task_type
    print(
        f"TASKING {type} : {char.name} {char.task} {char.task_type} {char.task_progress}/{char.task_total}"
    )

    # 1. si pas de task -> en prendre une
    if char.task == "" or char.task is None:
        if type == "items":
            await char.mover.to_coords(*task_items)
        else:
            await char.mover.to_coords(*task_fight)

        # accept new task
        await char.tasker.accept()

    resource = char.task
    needed = char.task_total - char.task_progress

    if needed <= 0:
        if type == "items":
            await char.mover.to_coords(*task_items)  # go to task npc items
        else:
            await char.mover.to_coords(*task_fight)  # go to task npc fight

        await char.tasker.complete()
        await char.sync()
        print(f"✅ Tâche {char.task} accomplie.")
        return

    if char.task_type == "items":
        bank_qty = char.account.bank.quantity(char.task)

        if bank_qty >= needed:
            while char.task_progress < char.task_total:
                await char.mover.to_bank()
                to_deposit = [
                    {"code": item["code"], "quantity": item["quantity"]}
                    for item in char.inventory
                    if item.get("code") and item.get("quantity", 0) > 0
                ]
                if len(to_deposit) > 0:
                    await char.banker.deposit(to_deposit)

                inventory_quantity = min(
                    (char.task_total - char.task_progress), char.inventory_max_items
                )
                to_withdraw = {"code": char.task, "quantity": inventory_quantity}
                await char.banker.withdraw([to_withdraw])

                await char.mover.to_coords(*task_items)
                await char.tasker.trade(to_withdraw)
                await char.sync()
        else:  # ressource needed is not fully available in bank, need to gather / craft
            await char.account.ensure_resource(resource, needed, requester=char)
            await char.sync()
            return

    else:
        if needed > 0:
            await char.account.ensure_resource(resource, needed, requester=char)
            await char.sync()
            return
