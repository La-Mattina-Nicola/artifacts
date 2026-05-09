from routines import gathering, fighting, crafting


def _make_task(fn, action: str, target: str):
    """Attache les métadonnées d'affichage à une fonction lambda."""
    fn._action = action
    fn._target = target
    return fn


async def handle_command(cmd, heroes, ctx, log_lines=None, logs_area=None):
    toggle_skills_overview = ctx.get("toggle_skills_overview")

    def log(msg: str):
        if log_lines is not None and logs_area is not None:
            log_lines.append(msg)
            logs_area.text = "\n".join(log_lines) + "\n"
            buf = logs_area.buffer
            buf.cursor_position = len(buf.text)
        else:
            print(msg)

    # ─────────────────────────────────────────────
    # COMMANDES GLOBALES (pas liées à un héros)
    # ─────────────────────────────────────────────
    if cmd == "show characters details":
        if toggle_skills_overview:
            toggle_skills_overview(True)
            log("📊 Affichage des métiers activé")
        else:
            log("❌ toggle_skills_overview non disponible")
        return

    if cmd == "hide characters details":
        if toggle_skills_overview:
            toggle_skills_overview(False)
            log("📄 Retour au dashboard")
        else:
            log("❌ toggle_skills_overview non disponible")
        return

    # ─────────────────────────────────────────────
    # COMMANDES HÉROS (hero action code)
    # ─────────────────────────────────────────────
    parts = cmd.split()
    if len(parts) < 3:
        log("❌ Format attendu : <hero> <action> <code>")
        return

    hero_name, action, code = parts[0], parts[1], parts[2]

    hero = next((h for h in heroes if h.name == hero_name), None)
    if not hero:
        log(f"❌ Hero '{hero_name}' introuvable")
        return

    if action == "fight":
        hero.default_task = _make_task(lambda: fighting(hero, code), "fight", code)
        log(f"⚔️  {hero.name} combat maintenant {code}")

    elif action == "gather":
        hero.default_task = _make_task(lambda: gathering(hero, code), "gather", code)
        log(f"⛏️  {hero.name} gather maintenant {code}")

    elif action == "craft":
        hero.default_task = _make_task(
            lambda: crafting(hero, code, 9999), "craft", code
        )
        log(f"🛠️  {hero.name} craft maintenant {code}")

    else:
        log(f"❌ Action inconnue : {action}")
