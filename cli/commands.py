from routines import gathering, fighting, crafting
from models import Character


def _make_task(char, fn, *args):
    """Attache les métadonnées d'affichage à une fonction lambda."""
    match fn.__name__:
        case "fighting":
            picto = "⚔️"
        case "gathering":
            picto = "⚒️"
        case "crafting":
            picto = "🔧"
        case _:
            picto = "❓"

    def my_fn():
        return fn(char, *args)

    my_fn._action = picto
    my_fn._target = args[0] if args else "???"
    return my_fn


# ─────────────────────────────────────────────
# DICTIONNAIRES DE COMMANDES
# ─────────────────────────────────────────────


def _cancel_current(hero):
    """Annule la coroutine en cours si elle tourne."""
    t = getattr(hero, "_current_task", None)
    if t and not t.done():
        t.cancel()


def _stop_routine(hero):
    """Arrête la routine actuelle du héros."""
    hero.default_task = None
    _cancel_current(hero)
    return f"⏸️ {hero.name} en attente"


def _fight_routine(hero, code):
    """Démarre une routine de combat."""
    hero.default_task = _make_task(hero, fighting, code)
    _cancel_current(hero)
    return f"⚔️ {hero.name} combat {code}"


def _gather_routine(hero, code):
    """Démarre une routine de récolte."""
    hero.default_task = _make_task(hero, gathering, code)
    _cancel_current(hero)
    return f"⛏️ {hero.name} récolte {code}"


def _craft_routine(hero, code, obj=1):
    """Démarre une routine de craft."""
    hero.default_task = _make_task(hero, crafting, code, int(obj))
    _cancel_current(hero)
    return f"🔧 {hero.name} craft {code}"


async def _add_task(account, target, quantity=1, priority=10):
    await account.add_request(target, int(quantity), int(priority))
    return f"📋 Requête : {quantity}x {target}"


# Dictionnaire des actions héros (sans paramètre)
dict_hero_actions_no_param = {
    "stop": _stop_routine,
}

# Dictionnaire des actions héros (avec paramètre)
dict_hero_actions_with_param = {
    "fight": _fight_routine,
    "gather": _gather_routine,
    "craft": _craft_routine,
}

# Dictionnaire des commandes globales
dict_global_commands = {
    "stop": "stop",
    "show characters details": "show_details",
    "hide characters details": "hide_details",
}


async def handle_command(cmd, heroes, ctx, log_lines=None, logs_area=None):
    """Traite une commande CLI."""
    toggle_skills_overview = ctx.get("toggle_skills_overview")

    def log(msg: str):
        """Affiche un message dans les logs ou print."""
        if log_lines is not None and logs_area is not None:
            log_lines.append(msg)
            logs_area.text = "\n".join(log_lines) + "\n"
            buf = logs_area.buffer
            buf.cursor_position = len(buf.text)
        else:
            print(msg)

    cmd = cmd.strip()
    if not cmd:
        return

    # ─────────────────────────────────────────────
    # COMMANDES GLOBALES
    # ─────────────────────────────────────────────
    if cmd in dict_global_commands:
        if cmd == "show characters details":
            if toggle_skills_overview:
                toggle_skills_overview(True)
                log("📊 Affichage des métiers activé")
            else:
                log("❌ toggle_skills_overview non disponible")
        elif cmd == "hide characters details":
            if toggle_skills_overview:
                toggle_skills_overview(False)
                log("📄 Retour au dashboard")
            else:
                log("❌ toggle_skills_overview non disponible")
        return

    # ─────────────────────────────────────────────
    # COMMANDES HÉROS
    # ─────────────────────────────────────────────
    parts = cmd.split()
    # Format : "add task <target> [quantity] [priority]"
    if parts[0] == "add" and parts[1] == "task":
        target = parts[2] if len(parts) > 2 else None
        quantity = parts[3] if len(parts) > 3 else 1
        priority = parts[4] if len(parts) > 4 else 10
        if not target:
            log("❌ Format : add task <item_code> [quantity] [priority]")
            return
        account = ctx.get("account")
        if not account:
            log("❌ Account non disponible dans le contexte")
            return
        result = await _add_task(account, target, quantity, priority)
        log(result)
        return
    if len(parts) < 2:
        log("❌ Format attendu : <hero> <action> [code]")
        return

    hero_name = parts[0]
    action = parts[1].lower()
    code = parts[2] if len(parts) > 2 else None
    extra = parts[3] if len(parts) > 3 else None

    # Trouve le héros
    hero = next((h for h in heroes if h.name == hero_name), None)
    if not hero:
        log(f"❌ Héros '{hero_name}' introuvable")
        return

    # Exécute l'action sans paramètre
    if action in dict_hero_actions_no_param:
        result = dict_hero_actions_no_param[action](hero)
        log(result)
        return

    # Exécute l'action avec paramètre
    if action in dict_hero_actions_with_param:
        if not code:
            log(f"❌ L'action '{action}' nécessite un paramètre (code)")
            return
        if extra is not None:
            result = dict_hero_actions_with_param[action](hero, code, extra)
        else:
            result = dict_hero_actions_with_param[action](hero, code)
        log(result)
        return

    # Action inconnue
    log(f"❌ Action inconnue : {action}")
