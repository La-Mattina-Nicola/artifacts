import asyncio
from models.character import Character
from .utils import cancellable


@cancellable
async def tasking(char: Character, type="items"):
    """
    Phase 3.2: Complete tasking loop per plan.

    1. Fetch task from server (if none, accept new)
    2. Check if resources available (total_available >= needed)
    3. If not enough → call add_request + sleep 5s
    4. If enough → loop: withdraw → move → trade → repeat
    5. When progress == total → complete task at taskmaster
    """

    # =====================================================================
    # STEP 1: Fetch task from server
    # =====================================================================
    print(f"🎯 Tasking ! {char.name}")
    await char.sync()

    # If no active task, fetch a new one
    if not char.task:
        print(f"📋 {char.name} — Chercher une nouvelle tâche...")
        taskmaster_pos = char.world_map.get_nearest_taskmaster(type, (char.x, char.y))
        if taskmaster_pos:
            await char.mover.to_coords(*taskmaster_pos)
        success = await char.tasker.new()
        if not success:
            print(f"❌ {char.name} — Impossible de récupérer une nouvelle tâche")
        return

    target_item = char.task
    task_type = char.task_type
    progress = char.task_progress
    total = char.task_total

    print(f"{char.name} | {target_item} {task_type} {progress}/{total}")

    # =====================================================================
    # STEP 2: Handle different task types
    # =====================================================================

    if task_type == "monsters":
        # Monster tasks: delegate to add_request (they stay server-side)
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
            print(f"⚔️ {char.name} — Besoin de {remaining}x {target_item}")
            await char.account.add_request(target_item, remaining, char.name)
        return

    # =====================================================================
    # STEP 3a: Item tasks - Check resource availability
    # =====================================================================
    elif task_type == "items":
        needed = total - progress
        available = char.account.total_available(target_item)

        print(
            f"📦 {char.name} — Besoin: {needed}x {target_item} (dispo: {available}/{total})"
        )

        if available < needed:
            # Not enough resources - request collection
            missing = needed - available
            print(
                f"⏳ {char.name} — Manque {missing}x {target_item}, générisation des tâches collection..."
            )
            await char.account.add_request(target_item, missing, char.name)
            print(f"⏸️ {char.name} — Tasks créées, main_loop() les exécutera...")
            await asyncio.sleep(3) # sleep de prévention pour avoir le temps de créer une task
            return

        # =====================================================================
        # STEP 3b: Resources ready - Loop: withdraw → move → trade → repeat
        # =====================================================================
        print(f"✅ {char.name} — Ressources prêtes! Livraison en cours...")

        # Move to bank first
        await char.mover.to_bank()

        # Clear inventory of other items to make space
        to_deposit = [
            {"code": item["code"], "quantity": item["quantity"]}
            for item in char.inventory
            if item.get("code")
            and item.get("quantity", 0) > 0
            and item["code"] != target_item
        ]
        if to_deposit:
            try:
                await char.banker.deposit(to_deposit)
                print(f"✅ {char.name} — Inventaire purgé")
            except Exception as e:
                print(f"⚠️ {char.name} — Erreur dépôt: {e}")
                await asyncio.sleep(1)
                return

        # Loop: withdraw → trade until all delivered
        remaining = needed
        attempt_count = 0

        while remaining > 0:
            # Calculate how much we can carry
            current_used = sum(
                item.get("quantity", 0) for item in char.inventory if item.get("code")
            )
            available_space = char.inventory_max_items - current_used
            batch_size = min(available_space, remaining)

            if batch_size <= 0:
                print(f"⚠️ {char.name} — Inventaire plein, syncing...")
                await char.sync()
                await asyncio.sleep(2)
                attempt_count += 1
                if attempt_count > 10:
                    print(
                        f"❌ {char.name} — Inventaire reste plein après 10 tentatives!"
                    )
                    return
                continue

            # ===================================================================
            # Step 3b-i: Withdraw from bank
            # ===================================================================
            print(f"🏧 {char.name} — Retrait {batch_size}x {target_item}...")
            withdraw_success = await char.withdrawer.withdraw(
                [{"code": target_item, "quantity": batch_size}]
            )

            if not withdraw_success:
                print(f"❌ {char.name} — Échec du retrait")
                await asyncio.sleep(2)
                continue

            await char.sync()

            # ===================================================================
            # Step 3b-ii: Move to taskmaster location
            # ===================================================================
            taskmaster_pos = char.world_map.get_nearest_taskmaster(
                type, (char.x, char.y)
            )
            if taskmaster_pos:
                print(f"🗺️ {char.name} — Trajet vers taskmaster...")
                await char.mover.to_coords(*taskmaster_pos)

            # ===================================================================
            # Step 3b-iii: Trade with NPC
            # ===================================================================
            print(f"💱 {char.name} — Trade {batch_size}x {target_item}...")
            trade_body = {"code": target_item, "quantity": batch_size}
            trade_success = await char.tasker.trade(trade_body)

            if not trade_success:
                print(f"❌ {char.name} — Échec du trade")
                await asyncio.sleep(2)
                continue

            # Update state after trade
            await char.sync()
            remaining -= batch_size

            print(f"✅ {char.name} — Trade succès! Remaining: {remaining}")

            attempt_count = 0  # Reset counter on success

        # =====================================================================
        # STEP 4: Complete task at taskmaster
        # =====================================================================
        print(f"🎉 {char.name} — Tous les items livrés! Complétion de la tâche...")
        taskmaster_pos = char.world_map.get_nearest_taskmaster(type, (char.x, char.y))
        if taskmaster_pos:
            await char.mover.to_coords(*taskmaster_pos)

        complete_success = await char.tasker.complete()
        if complete_success:
            print(f"✅ {char.name} — Tâche complétée avec succès!")
        else:
            print(f"❌ {char.name} — Erreur lors de la complétion")
