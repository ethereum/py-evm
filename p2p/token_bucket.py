import asyncio
import time
from typing import (
    Union,
    AsyncGenerator,
)


class NotEnoughTokens(Exception):
    """
    Raised if the token bucket is empty when trying to take a token in blocking
    mode.
    """
    pass


class TokenBucket:
    def __init__(self,
                 rate: Union[int, float],
                 capacity: Union[int, float]) -> None:
        self._rate = rate
        self._capacity = capacity
        self._num_tokens = self._capacity
        self._last_refill = time.perf_counter()
        self._seconds_per_token = 1 / self._rate
        self._take_lock = asyncio.Lock()

    async def __aiter__(self) -> AsyncGenerator[None, None]:
        """
        Can be used as an async iterator to limit the rate at which a loop can
        run.
        """
        while True:
            await self.take()
            yield

    def get_num_tokens(self) -> float:
        """
        Return the number of tokens current in the bucket.
        """
        return max(0, self._get_num_tokens(time.perf_counter()))

    def _get_num_tokens(self, when: float) -> float:
        # Note that the implementation of the `take` method requires that this
        # function to allow negative results..
        return min(
            self._capacity,
            self._num_tokens + (self._rate * (when - self._last_refill)),
        )

    def _take(self, num: Union[int, float] = 1) -> None:
        now = time.perf_counter()
        if num < 0:
            raise ValueError("Cannot take negative token quantity")

        # refill the bucket
        self._num_tokens = self._get_num_tokens(now)
        self._last_refill = now

        # deduct the requested tokens.  this operation is allowed to result in
        # a negative internal representation of the number of tokens in the
        # bucket.
        self._num_tokens -= num

    async def take(self, num: Union[int, float] = 1) -> None:
        """
        Take `num` tokens out of the bucket.  If the bucket does not have
        enough tokens, blocks until the bucket will be full enough to fulfill
        the request.
        """
        # the lock ensures that we don't have two processes take from the
        # bucket at the same time while the inner sleep is happening
        async with self._take_lock:
            self._take(num)

        # if the bucket balance is negative, wait an amount of seconds
        # adequatet to fill it.  Note that this requires that `_get_num_tokens`
        # be able to return a negative value.
        if self._num_tokens < 0:
            sleep_for = abs(self._num_tokens) * self._seconds_per_token
            await asyncio.sleep(sleep_for)

    def take_nowait(self, num: Union[int, float] = 1) -> None:
        # we calculate this value locally to ensure that in the case of not
        # having enough tokens the error message is accurate due to race
        # condition between calculating capacity and raising the error message.
        num_tokens = self.get_num_tokens()
        if num_tokens >= num:
            self._take(num)
        else:
            raise NotEnoughTokens(
                f"Insufficient capacity.  Needed {num:.2f} but only has {num_tokens:.2f}"
            )

    def can_take(self, num: Union[int, float] = 1) -> bool:
        """
        Return boolean whether the bucket has enough tokens to take `num` tokens.
        """
        return num <= self.get_num_tokens()
