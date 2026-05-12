import os
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
        print("🚀 Initialisation du compte...")

        account = Account(token=os.getenv("ARTIFACTS_TOKEN"))
        await account.initialize()
        ctx["account"] = account

        # ← ici
        _spawn_task(account.listen_completions(), "listen_completions", hero_tasks)

        ctx["items_manager"] = account.items_db
        ctx["world_map"] = account.world

        default_tasks = {
            "Kioyaa": (fighting, ["mushmush"]),
            "Kioyaa_g": (tasking, ["monsters"]),
            "Kio_wood": (tasking, ["monsters"]),
            "Kio_fish": (tasking, ["monsters"]),
            "Kio_util": (tasking, ["monsters"]),
        }

        for key, value in default_tasks.items():
            char = account.add_character(key)
            heroes.append(char)
            await char.sync()
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
