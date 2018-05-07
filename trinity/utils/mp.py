import asyncio
import functools
import multiprocessing
import os
from typing import Callable, Any


MP_CONTEXT = os.environ.get('TRINITY_MP_CONTEXT', 'spawn')


# sets the type of process that multiprocessing will create.
ctx = multiprocessing.get_context(MP_CONTEXT)


def async_method(method_name: str) -> Callable[..., Any]:
    async def method(self, *args, **kwargs):
        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            None,
            functools.partial(self._callmethod, kwds=kwargs),
            method_name,
            args,
        )
    return method


def sync_method(method_name: str) -> Callable[..., Any]:
    def method(self, *args, **kwargs):
        return self._callmethod(method_name, args, kwargs)
    return method
