import asyncio
import logging
import os
import signal
from typing import (
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Tuple,
)

from async_generator import asynccontextmanager
from async_timeout import timeout


class AsyncProcessRunner():
    logger = logging.getLogger("trinity.tools.async_process_runner.AsyncProcessRunner")
    proc: asyncio.subprocess.Process

    @classmethod
    @asynccontextmanager
    async def run(cls,
                  cmds: Tuple[str, ...],
                  timeout_sec: int = 10) -> AsyncIterator['AsyncProcessRunner']:
        try:
            async with timeout(timeout_sec):
                runner = cls()
                runner.proc = await asyncio.create_subprocess_exec(
                    *cmds,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE,
                    # We need this because Trinity spawns multiple processes and we need to
                    # take down the entire group of processes.
                    preexec_fn=os.setsid,
                )
                yield runner
                runner.kill()
        except asyncio.TimeoutError:
            runner.kill()

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
            try:
                line = await awaitable_bytes_fn()
            except asyncio.CancelledError:
                # Return to keep the consumer of the AsyncIterable running
                return
            self.logger.debug(line)
            if line == b'':
                return
            else:
                yield line.decode('utf-8')

    def kill(self, sig: int = signal.SIGKILL) -> None:
        try:
            os.killpg(os.getpgid(self.proc.pid), sig)
        except ProcessLookupError:
            self.logger.info("Process %s has already disappeared", self.proc.pid)
