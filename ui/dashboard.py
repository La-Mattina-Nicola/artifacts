from datetime import datetime, timezone
import unicodedata

LINE_W = 17

SKILLS = [
    "mining",
    "woodcutting",
    "fishing",
    "weaponcrafting",
    "gearcrafting",
    "jewelrycrafting",
    "cooking",
    "alchemy",
]
# Icônes U+1F000+ uniquement → east_asian_width='W' → 2 cols terminal, garanti
# Aucun variation selector (U+FE0F) qui perturbe le comptage
_SKILL_SHORT = {
    "mining": "⛏",
    "woodcutting": "🪓",
    "fishing": "🎣",
    "weaponcrafting": "🗡",
    "gearcrafting": "🛡",
    "jewelrycrafting": "💎",
    "cooking": "🍳",
    "alchemy": "🧪",
}

ICON_COLS = 2  # toutes nos icônes = Wide = 2 colonnes terminal
LINE_W = 17
_TEXT_W = LINE_W - ICON_COLS  # = 15 chars ASCII après l'icône


def render_hero_block(hero, show_skills: bool = False) -> list[str]:
    if hero.default_task is None:
        action, target = "Waiting ...", ""
    else:
        action = getattr(hero.default_task, "_action", "TASK")
        target = getattr(hero.default_task, "_target", "?")

    cd = _get_cd_remaining(hero)
    _TARGET_W = _TEXT_W - (len(action) + 2)  # 12
    action_line = f"{action}   {target[:_TARGET_W]:<{_TARGET_W}}"
    action_line = f"{action_line:<18}"
    lines = [
        f"{hero.name[:10]:<10} lv{hero.level:>4}",
        _ljust_display(f"HP {hero.hp}/{hero.max_hp}", LINE_W),
        action_line,  # icône+15 = 17 ✓
        _ljust_display(f"CD {cd:4.1f}s", LINE_W),
    ]

    if show_skills:
        for skill in SKILLS:
            lvl = getattr(hero, f"{skill}_level", 0)
            xp = getattr(hero, f"{skill}_xp", 0)
            max_xp = getattr(hero, f"{skill}_max_xp", 1) or 1
            pct = xp / max_xp * 100
            icon = _SKILL_SHORT[skill]

            # icône (2 cols) + 15 chars ASCII = 17 cols total
            # " lv "(4) + level(3) + "  "(2) + pct(5) + "%"(1) = 15 ✓
            if _display_width(icon) == 1:
                icon = f"{icon} "
            res = f"{icon}    {lvl:>3}  {pct:>5.1f}%"
            lines.append(res)

    return lines


def _display_width(s: str) -> int:
    """Largeur d'affichage réelle (les emojis/wide chars comptent pour 2)."""
    w = 0
    for ch in s:
        cp = ord(ch)
        # Variation selectors (U+FE00–U+FE0F) : zero-width dans le terminal
        if 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
            continue
        # Autres caractères zero-width (combining marks, format chars)
        if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
            continue
        eaw = unicodedata.east_asian_width(ch)
        w += 2 if eaw in ("W", "F") else 1
    return w


def _ljust_display(s: str, width: int, fill: str = " ") -> str:
    """ljust basé sur la largeur d'affichage, pas len()."""
    pad = width - _display_width(s)
    res = s + fill * max(pad, 0)
    return res


def _get_cd_remaining(hero) -> float:
    exp_raw = getattr(hero, "cooldown_expiration", None)
    if not exp_raw:
        return 0.0
    try:
        if isinstance(exp_raw, str):
            exp = datetime.fromisoformat(exp_raw.replace("Z", "+00:00"))
        elif isinstance(exp_raw, datetime):
            exp = exp_raw if exp_raw.tzinfo else exp_raw.replace(tzinfo=timezone.utc)
            exp = exp.astimezone(timezone.utc)
        else:
            return 0.0
        return max(0.0, (datetime.now(timezone.utc) - exp).total_seconds() * -1)
    except Exception:
        return 0.0


def build_dashboard_text(heroes, show_skills: bool = False) -> str:
    if not heroes:
        return "⏳ Initialisation..."

    blocks = [render_hero_block(h, show_skills) for h in heroes]
    n_lines = 12 if show_skills else 4

    rows = []
    for i in range(n_lines):
        rows.append(" | ".join(block[i] for block in blocks))

    return "\n".join(rows)


def build_skills_overview(heroes):
    return build_dashboard_text(heroes, show_skills=True)
