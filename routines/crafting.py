from models.character import Character


def _inv_count(char: Character, item_code: str) -> int:
    """Quantité d'un item dans l'inventaire du personnage."""
    return sum(
        i.get("quantity", 0) for i in char.inventory if i.get("code") == item_code
    )


def _inv_total(char: Character) -> int:
    return sum(i.get("quantity", 0) for i in char.inventory if i.get("code"))


async def crafting(char: Character, item_code: str, objectif: int = 1):
    """
    Routine de crafting autonome.

    - Calcule combien d'exemplaires peuvent être craftés avec les ressources
      disponibles (inventaire + banque).
    - Retire les matériaux de la banque si nécessaire.
    - Se déplace au bon workshop.
    - Craft par batchs en respectant la capacité de l'inventaire.
    - Dépose les résultats en banque et recommence jusqu'à atteindre `objectif`.

    Args:
        item_code: Code de l'item à crafter (ex: "iron_sword").
        objectif:  Nombre total d'exemplaires à crafter.
    """

    # ── 1. Récupérer la recette depuis la base d'items ──────────────────────
    item = char.items_db.get_by_code(item_code)
    if not item or not item.craft:
        print(f"❌ Recette introuvable pour '{item_code}'.")
        return

    craft_info = item.craft  # {"skill": "weaponcrafting", "level": 5, "items": [...]}
    skill = craft_info.get("skill")
    req_level = craft_info.get("level", 1)
    recipe = craft_info.get("items", [])  # [{"code": "iron", "quantity": 2}, ...]
    quantity_produced = craft_info.get("quantity", 1)  # items produits par craft

    if not recipe:
        print(f"❌ La recette de '{item_code}' est vide.")
        return

    # ── 2. Vérifier le niveau de skill du personnage ────────────────────────
    # Les skills sont stockés sur le personnage via sync() : {skill}_level
    # On re-sync pour avoir l'état frais.
    await char.sync()
    char_skill_level = getattr(char, f"{skill}_level", None)
    if char_skill_level is None:
        # Le skill n'est pas encore tracké sur le dataclass : on continue prudemment
        print(f"⚠️  Impossible de vérifier le niveau {skill}. On tente quand même.")
    elif char_skill_level < req_level:
        print(
            f"❌ {char.name} — Niveau {skill} insuffisant "
            f"({char_skill_level}/{req_level}) pour crafter {item_code}."
        )
        return

    # ── 3. Calculer combien d'exemplaires on peut faire ─────────────────────
    bank_content = char.banker.content  # Dict[str, int]

    def craftable_count() -> int:
        """Combien peut-on crafter avec l'inventaire + banque actuels ?"""
        limits = []
        for mat in recipe:
            code = mat["code"]
            needed_per_craft = mat["quantity"]
            available = _inv_count(char, code) + bank_content.get(code, 0)
            limits.append(available // needed_per_craft)
        return min(limits) * quantity_produced if limits else 0

    total_craftable = craftable_count()
    remaining = min(objectif, total_craftable)

    if remaining <= 0:
        # Calcul du manque pour aider au debug
        missing = []
        for mat in recipe:
            have = _inv_count(char, mat["code"]) + bank_content.get(mat["code"], 0)
            need = mat["quantity"]
            if have < need:
                missing.append(f"{mat['code']} (have {have}, need {need})")
        print(
            f"⚠️  {char.name} — Pas assez de matériaux pour {item_code}. Manque : {', '.join(missing)}"
        )
        return

    print(
        f"🔧 {char.name} — Objectif : {objectif}x {item_code}. Craftable maintenant : {total_craftable}."
    )

    crafted_total = 0

    while crafted_total < remaining:
        # ── 4. Vider l'inventaire à la banque ──────────────────────────────
        await char.mover.to_bank()

        # Déposer TOUT ce qui est en inventaire
        all_items = [
            {"code": i["code"], "quantity": i["quantity"]}
            for i in char.inventory
            if i.get("code") and i.get("quantity", 0) > 0
        ]
        if all_items:
            await char.banker.deposit(all_items)
        await char.sync()

        # ── 5. Calculer le batch ──────────────────────────────────────────
        batch_remaining = (remaining - crafted_total) // quantity_produced

        # Limiter par la place en inventaire disponible
        free_slots = char.inventory_max_items - _inv_total(char)

        # Vérifier qu'on peut retirer les matériaux ET stocker les résultats
        mats_per_batch = sum(mat["quantity"] for mat in recipe)
        batch_by_inv = max(1, free_slots // max(mats_per_batch, quantity_produced))

        batch = min(batch_by_inv, batch_remaining)  # Prendre le maximum possible

        # ── 6. Retirer les matériaux exactement nécessaires ────────────────
        to_withdraw = []
        for mat in recipe:
            code = mat["code"]
            needed = mat["quantity"] * batch
            available_in_bank = char.banker.content.get(code, 0)
            to_take = min(needed, available_in_bank)
            if to_take > 0:
                to_withdraw.append({"code": code, "quantity": to_take})
            else:
                print(f"⚠️  Banque : {code} épuisé. Arrêt du crafting.")
                return

        ok = await char.banker.withdraw(to_withdraw)
        if not ok:
            print(f"❌ Retrait banque échoué pour {char.name}.")
            return
        await char.sync()

        # ── 7. Trouver et rejoindre le workshop ─────────────────────────────
        workshop_pos = char.world_map.get_nearest_workshop(skill, (char.x, char.y))
        if not workshop_pos:
            print(f"❌ Aucun workshop '{skill}' trouvé sur la map.")
            return

        await char.mover.to_coords(*workshop_pos)

        # ── 8. Crafter ──────────────────────────────────────────────────────
        success = await char.craft(item_code, quantity=batch)
        if not success:
            print(f"❌ Crafting échoué. Abandon.")
            return

        crafted_total += batch * quantity_produced
        print(f"✅ {char.name} — {crafted_total}/{remaining}x {item_code} craftés.")
        await char.sync()

        # ── 9. Dépôt en banque si inventaire proche du plein ────────────────
        if char.inventory_is_full(margin=5):
            await char.mover.to_bank()
            items_to_deposit = [
                {"code": i["code"], "quantity": i["quantity"]}
                for i in char.inventory
                if i.get("code") and i.get("quantity", 0) > 0
            ]
            if items_to_deposit:
                await char.banker.deposit(items_to_deposit)
                await char.sync()

    print(f"🎉 {char.name} — Objectif atteint : {crafted_total}x {item_code} craftés !")
