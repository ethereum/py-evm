import asyncio
from typing import Any, Awaitable, cast, List  # noqa: F401

from p2p.exceptions import OperationCancelled


class CancelToken:

    def __init__(self, name: str) -> None:
        self.name = name
        self._chain = []  # type: List['CancelToken']
        self._triggered = asyncio.Event()

    def chain(self, token: 'CancelToken') -> 'CancelToken':
        """Return a new CancelToken chaining this and the given token.

        The new CancelToken's triggered will return True if trigger() has been
        called on either of the chained tokens, but calling trigger() on the new token
        has no effect on either of the chained tokens.
        """
        chain_name = ":".join([self.name, token.name])
        chain = CancelToken(chain_name)
        chain._chain.extend([self, token])
        return chain

    def trigger(self) -> None:
        self._triggered.set()

    @property
    def triggered_token(self) -> 'CancelToken':
        if self._triggered.is_set():
            return self
        for token in self._chain:
            if token.triggered:
                # Use token.triggered_token here to make the lookup recursive as self._chain may
                # contain other chains.
                return token.triggered_token
        return None

    @property
    def triggered(self) -> bool:
        if self._triggered.is_set():
            return True
        return any(token.triggered for token in self._chain)

    async def wait(self) -> None:
        if self.triggered_token is not None:
            return

        futures = [asyncio.ensure_future(self._triggered.wait())]
        for token in self._chain:
            futures.append(asyncio.ensure_future(token.wait()))

        def cancel_pending(f):
            for future in futures:
                if not future.done():
                    future.cancel()

        fut = asyncio.ensure_future(_wait_for_first(futures))
        fut.add_done_callback(cancel_pending)
        await fut

    def __str__(self):
        return self.name


async def _wait_for_first(futures):
    for future in asyncio.as_completed(futures):
        await cast(asyncio.Future, future)
        return


async def wait_with_token(*futures: Awaitable,
                          token: CancelToken,
                          timeout: float = None) -> Any:
    """Wait for the first future to complete, unless we timeout or the cancel token is triggered.

    Returns the result of the first future to complete.

    Raises TimeoutError if we timeout or OperationCancelled if the cancel token is triggered.

    All pending futures are cancelled before returning.
    """
    done, pending = await asyncio.wait(
        futures + (token.wait(),),
        timeout=timeout,
        return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    if not done:
        raise TimeoutError()
    if token.triggered_token is not None:
        # We've been asked to cancel so we don't care about our future, but we must
        # consume its exception or else asyncio will emit warnings.
        for task in done:
            task.exception()
        raise OperationCancelled(
            "Cancellation requested by {} token".format(token.triggered_token))
    return done.pop().result()
