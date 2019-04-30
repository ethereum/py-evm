import asyncio
import logging
import os
import signal
from typing import (
    AsyncIterable,
    Awaitable,
    Callable,
    Tuple,
)


class AsyncProcessRunner():
    logger = logging.getLogger("trinity.tools.async_process_runner.AsyncProcessRunner")

    def __init__(self, debug_fn: Callable[[bytes], None] = None) -> None:
        self.debug_fn = debug_fn

    @classmethod
    async def create_and_run(cls,
                             cmds: Tuple[str, ...],
                             timeout_sec: int=10) -> 'AsyncProcessRunner':
        runner = cls()
        await runner.run(cmds, timeout_sec)
        return runner

    async def run(self, cmds: Tuple[str, ...], timeout_sec: int=10) -> None:
        proc = await asyncio.create_subprocess_exec(
            *cmds,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            # We need this because Trinity spawns multiple processes and we need to take down
            # the entire group of processes.
            preexec_fn=os.setsid,
        )
        self.proc = proc
        asyncio.ensure_future(self.kill_after_timeout(timeout_sec))

    @property
    async def stdout(self) -> AsyncIterable[str]:
        async for line in self._iterate_until_empty(self.proc.stdout.readline):
            yield line

    @property
    async def stderr(self) -> AsyncIterable[str]:
        async for line in self._iterate_until_empty(self.proc.stderr.readline):
            yield line

    async def _iterate_until_empty(
            self,
            awaitable_bytes_fn: Callable[[], Awaitable[bytes]]) -> AsyncIterable[str]:

        while True:
            line = await awaitable_bytes_fn()
            if self.debug_fn:
                self.debug_fn(line)
            if line == b'':
                return
            else:
                yield line.decode('utf-8')

    async def kill_after_timeout(self, timeout_sec: int) -> None:
        await asyncio.sleep(timeout_sec)
        self.kill()
        raise TimeoutError(f'Killed process after {timeout_sec} seconds')

    def kill(self, sig: int = signal.SIGKILL) -> None:
        try:
            os.killpg(os.getpgid(self.proc.pid), sig)
        except ProcessLookupError:
            self.logger.info("Process %s has already disappeared", self.proc.pid)
