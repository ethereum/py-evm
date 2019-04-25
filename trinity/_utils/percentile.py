import bisect
import collections
import math
from typing import List, Union, Deque


class Percentile:
    """
    Track a specific percentile across a window of recent data.

    https://en.wikipedia.org/wiki/Percentile
    """
    def __init__(self, percentile: float, window_size: int) -> None:
        if percentile < 0 or percentile > 1:
            raise ValueError("Invalid: percentile must be in the range [0, 1]")
        self.window: List[Union[int, float]] = []
        self.history: Deque[Union[int, float]] = collections.deque()
        self.percentile = percentile
        self.window_size = window_size

    @property
    def value(self) -> float:
        """
        The current approximation for the tracked percentile.
        """
        if not self.window:
            raise ValueError("No data for percentile calculation")

        idx = (len(self.window) - 1) * self.percentile
        if idx.is_integer():
            return self.window[int(idx)]

        left = int(math.floor(idx))
        right = int(math.ceil(idx))

        left_part = self.window[int(left)] * (right - idx)
        right_part = self.window[int(right)] * (idx - left)

        return left_part + right_part

    def update(self, value: Union[int, float]) -> None:
        bisect.insort(self.window, value)
        self.history.append(value)

        while len(self.history) > self.window_size:
            to_discard = self.history.popleft()
            window_idx = bisect.bisect_left(self.window, to_discard)
            discarded = self.window.pop(window_idx)
            if discarded != to_discard:
                raise ValueError(
                    "The value popped from the `window` does not match the "
                    "expected value"
                )
