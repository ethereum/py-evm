import math
from typing import Union


class StandardDeviation:
    """
    https://stackoverflow.com/questions/5543651/computing-standard-deviation-in-a-stream

    Tracks standard deviation on a stream of data.
    """
    def __init__(self) -> None:
        self.num_values = 0
        self.sum_of_values = 0.0
        self.sum_of_squared_values = 0.0

    def update(self, value: Union[int, float]) -> None:
        self.num_values += 1
        self.sum_of_values += value
        self.sum_of_squared_values += value ** 2

    @property
    def value(self) -> float:
        if self.num_values < 2:
            raise ValueError("No data")

        return math.sqrt(
            (self.num_values * self.sum_of_squared_values - self.sum_of_values ** 2) /
            (self.num_values * (self.num_values - 1))
        )
