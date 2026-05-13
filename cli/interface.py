import sys
import asyncio
import traceback
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit
from prompt_toolkit.layout.containers import FloatContainer, Float, ConditionalContainer
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.filters import has_focus, Condition

from .completer import GameCompleter
from .commands import handle_command
from ui.dashboard import build_dashboard_text, build_tasks_summary


class _StdoutToLogs:
    def __init__(self, log_lines, logs_area, get_app):
        self._log_lines = log_lines
        self._logs_area = logs_area
        self._get_app = get_app
        self._buf = ""

    def write(self, text: str):
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line and "\x1b" not in line and "\r" not in line:
                self._log_lines.append(line)
                joined = "\n".join(self._log_lines) + "\n"
                self._logs_area.text = joined
                self._logs_area.buffer.cursor_position = len(joined)
                try:
                    self._get_app().invalidate()
                except Exception:
                    pass

    def flush(self):
        pass

    def isatty(self):
        return False


async def run_cli(
    heroes: list,
    ctx: dict,
    *,
    world_map_key="world_map",
    items_manager_key="items_manager",
):
    log_lines = []

    # ── Zones de texte ────────────────────────────────────────────────────────
    logs_area = TextArea(
        text="",
        read_only=True,
        scrollbar=True,
        wrap_lines=False,
        focusable=False,
    )

    heroes_area = TextArea(
        text="⏳ Initialisation...",
        read_only=True,
        wrap_lines=False,  # tabulaire : pas de wrap sinon les colonnes se décalent
        focusable=False,
    )

    task_area = TextArea(
        text="",
        read_only=True,
        scrollbar=True,
        wrap_lines=True,
        focusable=False,
    )

    # ── Frames ────────────────────────────────────────────────────────────────

    heroes_frame = Frame(body=heroes_area, title="Heroes", width=99)
    task_frame = Frame(body=task_area, title="Task")

    # ── État du toggle (liste pour être capturé par les lambdas) ──────────────
    show_skills = [False]  # show_skills[0] est la source de vérité

    # ConditionalContainer : task_frame visible seulement si skills masqués
    task_container = ConditionalContainer(
        content=task_frame,
        filter=Condition(lambda: not show_skills[0]),
    )

    right_column = HSplit([heroes_frame, task_container])

    # ── Toggle exposé dans le contexte ───────────────────────────────────────
    def toggle_skills_overview(state: bool):
        show_skills[0] = state
        # Quand les skills sont affichés, heroes_frame prend toute la hauteur
        heroes_frame.height = None if state else 6
        try:
            app.invalidate()
        except Exception:
            pass

    ctx["toggle_skills_overview"] = toggle_skills_overview

    # ── Input / completer ────────────────────────────────────────────────────
    input_area = TextArea(
        height=1,
        prompt="> ",
        completer=None,
        complete_while_typing=True,
        multiline=False,
        focusable=True,
    )

    # ── Layout racine ─────────────────────────────────────────────────────────
    root = FloatContainer(
        content=HSplit(
            [
                VSplit(
                    [
                        Frame(body=logs_area, title="Logs", width=None),
                        right_column,
                    ],
                    padding=1,
                ),
                Frame(body=input_area, height=3),
            ]
        ),
        floats=[
            Float(
                xcursor=True,
                ycursor=True,
                content=CompletionsMenu(max_height=4, scroll_offset=1),
            )
        ],
    )

    # ── Key bindings ──────────────────────────────────────────────────────────
    kb = KeyBindings()
    app_holder = []

    def _append_log(msg: str):
        log_lines.append(msg)
        joined = "\n".join(log_lines) + "\n"
        logs_area.text = joined
        logs_area.buffer.cursor_position = len(joined)

    def _log_task_error(task: asyncio.Task, name: str):
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            _append_log(f"❌ Erreur dans {name}")
            for line in traceback.format_exception(type(exc), exc, exc.__traceback__):
                for part in line.rstrip().splitlines():
                    _append_log(part)
            try:
                app_holder[0].invalidate()
            except Exception:
                pass

    def _spawn_task(coro, name: str):
        task = asyncio.create_task(coro)
        task.add_done_callback(lambda t: _log_task_error(t, name))
        return task

    @kb.add("f2")
    def _(event):
        state = not show_skills[0]  # toggle
        show_skills[0] = state
        heroes_frame.height = None if state else 6

        if state:
            log_lines.append("📊 Affichage des métiers activé (F2)")
        else:
            log_lines.append("📄 Retour au dashboard (F2)")

        joined = "\n".join(log_lines) + "\n"
        logs_area.text = joined
        logs_area.buffer.cursor_position = len(joined)

        event.app.invalidate()

    @kb.add("enter", filter=has_focus(input_area))
    async def on_enter(event):
        cmd = input_area.text.strip()
        input_area.text = ""
        if not cmd:
            return
        _append_log(f"> {cmd}")
        _spawn_task(
            handle_command(cmd, heroes, ctx, log_lines, logs_area),
            f"handle_command:{cmd}",
        )

    @kb.add("c-c")
    @kb.add("c-q")
    def on_exit(event):
        event.app.exit()

    # ── Application ───────────────────────────────────────────────────────────
    layout = Layout(root, focused_element=input_area)
    app = Application(
        layout=layout, key_bindings=kb, full_screen=True, mouse_support=True
    )
    app_holder.append(app)

    # ── Boucle de rafraîchissement ────────────────────────────────────────────
    async def refresh_loop():
        while True:
            await asyncio.sleep(0.5)
            try:
                heroes_area.text = build_dashboard_text(
                    heroes, show_skills=show_skills[0]
                )
                account = ctx.get("account")
                if account:
                    task_area.text = build_tasks_summary(account)

                wm = ctx.get(world_map_key)
                im = ctx.get(items_manager_key)
                if wm and im and input_area.completer is None:
                    input_area.completer = GameCompleter(heroes, im, wm)

                app.invalidate()
            except Exception:
                _append_log("⚠️ refresh_loop arrete suite a une erreur")
                for line in traceback.format_exc().strip().splitlines():
                    _append_log(line)
                try:
                    app_holder[0].invalidate()
                except Exception:
                    pass
                break

    _real_stdout = sys.stdout
    _real_stderr = sys.stderr
    sys.stdout = _StdoutToLogs(log_lines, logs_area, lambda: app_holder[0])
    sys.stderr = _StdoutToLogs(log_lines, logs_area, lambda: app_holder[0])

    refresh_task = _spawn_task(refresh_loop(), "refresh_loop")
    try:
        await app.run_async()
    finally:
        sys.stdout = _real_stdout
        refresh_task.cancel()
