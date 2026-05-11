import asyncio
from models.character import Character
from .utils import cancellable


@cancellable
async def tasking(char: Character, type="items"):
    """
    Tasking routines
    """
    print(f"Tasking ! {char.name}")
    await char.sync()
    print(
        f"{char.name} | {char.task} {char.task_type} {char.task_progress}/{char.task_total}"
    )

    if not char.task:
        print(f"📋 {char.name} — Chercher une nouvelle tâche...")
        taskmaster_pos = char.world_map.get_nearest_taskmaster(type, (char.x, char.y))
        if taskmaster_pos:
            await char.mover.to_coords(*taskmaster_pos)
        await char.tasker.new()
        return

    target = char.task
    task_type = char.task_type
    progress = char.task_progress
    total = char.task_total

    if task_type == "monsters":
        if progress >= total:
            print(f"✅ {char.name} — Tâche monstre complétée ({progress}/{total})")
            taskmaster_pos = char.world_map.get_nearest_taskmaster(
                type, (char.x, char.y)
            )
            if taskmaster_pos:
                await char.mover.to_coords(*taskmaster_pos)
            await char.tasker.complete()
        else:
            remaining = total - progress
            print(f"⚔️ {char.name} — Besoin de {remaining}x {target}")
            await char.account.add_request(target, remaining, char.name)
            return


    elif task_type == "items":
        available = char.account.total_available(target)

        if available < total:
            missing = total - available
            print(
                f"📦 {char.name} — Besoin de {missing}x {target} (dispo: {available}/{total})"
            )
            await char.account.add_request(target, missing, char.name)
            print(f"⏸️ {char.name} — En pause 5s (attente gather/craft pour {target})")
            await asyncio.sleep(5)
            return

        print(f"💰 {char.name} — Livrer {total}x {target} ({progress}/{total})")

        await char.mover.to_bank()

        to_deposit = [
            {"code": i["code"], "quantity": i["quantity"]}
            for i in char.inventory
            if i.get("code") and i.get("quantity", 0) > 0 and i["code"] != target
        ]
        if to_deposit:
            try:
                await char.banker.deposit(to_deposit)
                print(f"✅ {char.name} — Dépôt effectué")
            except Exception as e:
                print(f"⚠️ {char.name} — Erreur dépôt: {e}")
                await asyncio.sleep(1)
                return

        remaining = total - progress
        attempt_count = 0
        max_attempts_per_batch = 5

        while remaining > 0:
            current_used = sum(
                item.get("quantity", 0) for item in char.inventory if item.get("code")
            )
            available_space = char.inventory_max_items - current_used
            batch = min(available_space, remaining)

            if batch <= 0:
                print(
                    f"⚠️ {char.name} — Inventaire plein (utilisé: {current_used}/{char.inventory_max_items})"
                )
                await char.sync()
                await asyncio.sleep(2)
                attempt_count += 1
                if attempt_count > 10:
                    print(
                        f"❌ {char.name} — Inventaire toujours plein après 10 tentatives"
                    )
                    return
                continue

            attempt_count = 0 

            try:
                await char.banker.withdraw([{"code": target, "quantity": batch}])
                print(f"✅ {char.name} — Retiré {batch}x {target}")
            except Exception as e:
                print(f"❌ {char.name} — Erreur retrait: {e}")
                await asyncio.sleep(2)
                attempt_count += 1
                if attempt_count > max_attempts_per_batch:
                    print(
                        f"❌ {char.name} — Retrait impossible après {max_attempts_per_batch} tentatives"
                    )
                    return
                continue

            taskmaster_pos = char.world_map.get_nearest_taskmaster(
                type, (char.x, char.y)
            )
            if taskmaster_pos:
                await char.mover.to_coords(*taskmaster_pos)

            try:
                await char.tasker.trade({"code": target, "quantity": batch})
                print(f"✅ {char.name} — Livré {batch}x {target}")
                remaining -= batch
            except Exception as e:
                print(f"❌ {char.name} — Erreur trade: {e}")
                await asyncio.sleep(2)
                attempt_count += 1
                if attempt_count > max_attempts_per_batch:
                    print(
                        f"❌ {char.name} — Trade impossible après {max_attempts_per_batch} tentatives"
                    )
                    return
                continue

        await char.sync()
        if char.task_progress >= char.task_total:
            try:
                await char.tasker.complete()
                print(f"✅ {char.name} — Tâche complétée!")
            except Exception as e:
                print(f"❌ {char.name} — Erreur complétion: {e}")
                await asyncio.sleep(2)
