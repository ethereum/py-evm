import collections
import math
from typing import Union, Deque


class StandardDeviation:
    """
    https://stackoverflow.com/questions/5543651/computing-standard-deviation-in-a-stream

    Tracks standard deviation on a stream of data.
    """
    def __init__(self, window_size: int) -> None:
        self.window: Deque[Union[int, float]] = collections.deque()
        self.window_size = window_size

    def update(self, value: Union[int, float]) -> None:
        self.window.append(value)

        while len(self.window) > self.window_size:
            self.window.popleft()

    @property
    def value(self) -> float:
        num_values = len(self.window)

        if num_values < 2:
            raise ValueError("No data")

        sum_of_values = sum(self.window)
        sum_of_squared_values = sum(item * item for item in self.window)

        return math.sqrt(
            (num_values * sum_of_squared_values - sum_of_values ** 2) /
            (num_values * (num_values - 1))
        )
