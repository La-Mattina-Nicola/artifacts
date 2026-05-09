import asyncio
import functools


def cancellable(fn):
    @functools.wraps(fn)
    async def wrapper(char, *args, **kwargs):
        task = asyncio.ensure_future(fn(char, *args, **kwargs))
        char._current_task = task
        try:
            await task
        except asyncio.CancelledError:
            print(f"⏸️ {char.name} — {fn.__name__} interrompu.")
        finally:
            char._current_task = None

    return wrapper
