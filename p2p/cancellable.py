from typing import (
    Awaitable,
    TypeVar,
)

from cancel_token import CancelToken


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
        return await token_chain.cancellable_wait(*awaitables, timeout=timeout)
