import os
import sys
import asyncio
import traceback
from contextlib import suppress
from dotenv import load_dotenv

from models.account import Account
from models import ItemsManager
from models import WorldMap
from routines import gathering, fighting, crafting, tasking

from cli.interface import run_cli
from cli.commands import _make_task

load_dotenv()


async def main():
    heroes = []
    ctx = {"items_manager": None, "world_map": None}
    hero_tasks = []
    stdout_ready = asyncio.Event()
    ctx["stdout_ready"] = stdout_ready
    bootstrap_logs = []
    ctx["bootstrap_logs"] = bootstrap_logs

    class _BootstrapStdout:
        def __init__(self, log_lines, real_stream):
            self._log_lines = log_lines
            self._real_stream = real_stream
            self._buf = ""

        def write(self, text: str):
            if self._real_stream:
                try:
                    self._real_stream.write(text)
                    if "\n" in text:
                        self._real_stream.flush()
                except Exception:
                    pass
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line:
                    self._log_lines.append(line)

        def flush(self):
            if self._real_stream:
                try:
                    self._real_stream.flush()
                except Exception:
                    pass

        def isatty(self):
            return False

    real_stdout = sys.stdout
    real_stderr = sys.stderr
    ctx["real_stdout"] = real_stdout
    ctx["real_stderr"] = real_stderr
    sys.stdout = _BootstrapStdout(bootstrap_logs, real_stdout)
    sys.stderr = _BootstrapStdout(bootstrap_logs, real_stderr)

    def _log_task_result(task: asyncio.Task, name: str):
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            print(f"❌ Tache echouee: {name}")
            traceback.print_exception(type(exc), exc, exc.__traceback__)

    def _spawn_task(coro, name: str, bucket=None):
        task = asyncio.create_task(coro, name=name)
        task.add_done_callback(lambda t: _log_task_result(t, name))
        if bucket is not None:
            bucket.append(task)
        return task

    loop = asyncio.get_running_loop()

    def _handle_exception(loop, context):
        msg = context.get("message", "Unhandled exception")
        print(f"⚠️ {msg}")
        exc = context.get("exception")
        if exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__)
        else:
            print(context)

    loop.set_exception_handler(_handle_exception)

    async def init_and_run():
        try:
            await asyncio.wait_for(stdout_ready.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
        print("🚀 Initialisation du compte...")

        account = Account(token=os.getenv("ARTIFACTS_TOKEN"))
        await account.initialize()
        ctx["account"] = account

        _spawn_task(account.listen_completions(), "listen_completions", hero_tasks)

        ctx["items_manager"] = account.items_db
        ctx["world_map"] = account.world
        ctx["bank"] = account.bank

        print(f"Bank copper_ore: {account.bank.quantity('copper_ore')}")

        default_tasks = {
            "Kioyaa": (tasking, ["items"]),
            "Kioyaa_g": (tasking, ["items"]),
            "Kio_wood": (tasking, ["items"]),
            "Kio_fish": (tasking, ["items"]),
            "Kio_util": (tasking, ["items"]),
        }

        for key, value in default_tasks.items():
            char = account.add_character(key)
            heroes.append(char)
            done = await char.sync()
            if done:
                char.default_task = _make_task(char, value[0], *value[1])
                _spawn_task(char.main_loop(), f"main_loop:{char.name}", hero_tasks)

        print(f"✅ {len(heroes)} héros sont en ligne !")

    init_task = _spawn_task(init_and_run(), "init_and_run")

    try:
        # L'UI démarre immédiatement ; stdout est redirigé dès maintenant
        await run_cli(
            heroes, ctx, world_map_key="world_map", items_manager_key="items_manager"
        )
    except Exception as e:
        traceback.print_exc()
        raise
    finally:
        init_task.cancel()
        for t in hero_tasks:
            t.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.gather(init_task, *hero_tasks, return_exceptions=True)
        print("\n🛑 Bot arrêté.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
