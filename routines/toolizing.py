from models.character import Character
from routines.utils import cancellable


@cancellable
async def toolizing(char: "Character", task_type: str):
    # go to bank.
    await char.mover.to_bank()
    await char.equiper.unequip(slot="weapon")
    await char.equip_best_tool_for_task(task_type)
    await char.sync()
