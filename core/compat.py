from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, Callable, TypeVar

T = TypeVar("T")


async def to_thread(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    native = getattr(asyncio, "to_thread", None)
    if native:
        return await native(func, *args, **kwargs)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))
