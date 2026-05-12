from models import Character
from .utils import cancellable
import asyncio

task_items = (4, 13)
task_fight = (1, 2)


@cancellable
async def tasking(char: "Character", type="items"):
    await char.sync()

    print(f"📋 {char.name} démarre une tâche de type {type}.")
    print(f"{char.task} {char.task_type} {char.task_progress}/{char.task_total}")

    if char.task == "" or char.task is None:
        if type == "items":
            await char.mover.to_coords(*task_items)
        else:
            await char.mover.to_coords(*task_fight)

        # accept new task
        await char.tasker.accept()

    doable = await char.account.is_task_doable(char, type)
    await asyncio.sleep(3)

    if not doable:
        print(f"❌ Tâche {char.task} non réalisable.")
        char.default_task = None
        return

    else:
        if type == "items":
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

                await char.mover.to_coords(*task_items)  # go to task npc items
                await char.tasker.trade(to_withdraw)
                await char.sync()
        else:
            await char.mover.to_coords(*task_fight)  # go to task npc fight

        if char.task_progress != char.task_total:
            print(
                f"⚠️ Tâche {char.task} en cours : {char.task_progress}/{char.task_total}"
            )
            char.default_task = None
            return
        await char.tasker.complete()

        await char.sync()

        print(f"✅ Tâche {char.task} accomplie.")
