import asyncio
from typing import (
    Any,
    Awaitable,
    cast,
    List,
    Sequence,
    TypeVar,
)

from p2p.exceptions import (
    EventLoopMismatch,
    OperationCancelled,
)


class CancelToken:

    def __init__(self, name: str, loop: asyncio.AbstractEventLoop = None) -> None:
        self.name = name
        self._chain: List['CancelToken'] = []
        self._triggered = asyncio.Event(loop=loop)
        self._loop = loop

    def chain(self, token: 'CancelToken') -> 'CancelToken':
        """Return a new CancelToken chaining this and the given token.

        The new CancelToken's triggered will return True if trigger() has been
        called on either of the chained tokens, but calling trigger() on the new token
        has no effect on either of the chained tokens.
        """
        if self._loop != token._loop:
            raise EventLoopMismatch("Chained CancelToken objects must be on the same event loop")
        chain_name = ":".join([self.name, token.name])
        chain = CancelToken(chain_name, loop=self._loop)
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

    def raise_if_triggered(self) -> None:
        if self.triggered:
            raise OperationCancelled(
                "Cancellation requested by {} token".format(self.triggered_token))

    async def wait(self) -> None:
        if self.triggered_token is not None:
            return

        futures = [asyncio.ensure_future(self._triggered.wait(), loop=self._loop)]
        for token in self._chain:
            futures.append(asyncio.ensure_future(token.wait(), loop=self._loop))

        def cancel_not_done(fut: 'asyncio.Future[None]') -> None:
            for future in futures:
                if not future.done():
                    future.cancel()

        async def _wait_for_first(futures: Sequence[Awaitable[Any]]) -> None:
            for future in asyncio.as_completed(futures):
                # We don't need to catch CancelledError here (and cancel not done futures)
                # because our callback (above) takes care of that.
                await cast(Awaitable[Any], future)
                return

        fut = asyncio.ensure_future(_wait_for_first(futures), loop=self._loop)
        fut.add_done_callback(cancel_not_done)
        await fut

    def __str__(self) -> str:
        return self.name


class CancellableMixin:
    cancel_token: CancelToken = None

    _TReturn = TypeVar('_TReturn')

    async def wait(self,
                   awaitable: Awaitable[_TReturn],
                   token: CancelToken = None,
                   timeout: float = None) -> _TReturn:
        """See wait_first()"""
        return await self.wait_first(awaitable, token=token, timeout=timeout)

    async def wait_first(self,
                         *awaitables: Awaitable[_TReturn],
                         token: CancelToken = None,
                         timeout: float = None) -> _TReturn:
        """
        Wait for the first awaitable to complete, unless we timeout or the token chain is triggered.

        The given token is chained with this service's token, so triggering either will cancel
        this.

        Returns the result of the first one to complete.

        Raises TimeoutError if we timeout or OperationCancelled if the token chain is triggered.

        All pending futures are cancelled before returning.
        """
        if token is None:
            token_chain = self.cancel_token
        else:
            token_chain = token.chain(self.cancel_token)
        return await wait_with_token(*awaitables, token=token_chain, timeout=timeout)


async def wait_with_token(*awaitables: Awaitable[Any],
                          token: CancelToken,
                          timeout: float = None) -> Any:
    """Wait for the first awaitable to complete, unless we timeout or the cancel token is triggered.

    Returns the result of the first one to complete.

    Raises TimeoutError if we timeout or OperationCancelled if the cancel token is triggered.

    All pending futures are cancelled before returning.
    """
    futures = [asyncio.ensure_future(a) for a in awaitables + (token.wait(),)]
    try:
        done, pending = await asyncio.wait(
            futures,
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED)
    except asyncio.futures.CancelledError:
        # Since we use return_when=asyncio.FIRST_COMPLETED above, we can be sure none of our
        # futures will be done here, so we don't need to check if any is done before cancelling.
        for future in futures:
            future.cancel()
        raise
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
