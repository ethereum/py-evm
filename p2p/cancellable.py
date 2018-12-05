from typing import (
    AsyncIterator,
    Awaitable,
    TypeVar,
)

from cancel_token import CancelToken

TReturn = TypeVar('TReturn')


class CancellableMixin:
    cancel_token: CancelToken = None

    async def wait(self,
                   awaitable: Awaitable[TReturn],
                   token: CancelToken = None,
                   timeout: float = None) -> TReturn:
        """See wait_first()"""
        return await self.wait_first(awaitable, token=token, timeout=timeout)

    async def wait_first(self,
                         *awaitables: Awaitable[TReturn],
                         token: CancelToken = None,
                         timeout: float = None) -> TReturn:
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
        return await token_chain.cancellable_wait(*awaitables, timeout=timeout)

    async def wait_iter(
            self,
            aiterable: AsyncIterator[TReturn],
            token: CancelToken = None,
            timeout: float = None) -> AsyncIterator[TReturn]:
        """
        Iterate through an async iterator, raising the OperationCancelled exception if the token is
        triggered. For example:

        ::

            async for val in self.wait_iter(my_async_iterator()):
                do_stuff(val)

        See :meth:`CancellableMixin.wait_first` for using arguments ``token`` and ``timeout``
        """
        aiter = aiterable.__aiter__()
        while True:
            try:
                yield await self.wait(
                    aiter.__anext__(),
                    token=token,
                    timeout=timeout,
                )
            except StopAsyncIteration:
                break
