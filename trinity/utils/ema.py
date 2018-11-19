from typing import Union

from eth_utils import ValidationError


class EMA:
    """
    Represents an exponential moving average.
    https://en.wikipedia.org/wiki/Moving_average#Exponential_moving_average

    Smoothing factor, or "alpha" of the exponential moving average.

    - Closer to 0 gives you smoother, slower-to-update, data
    - Closer to 1 gives you choppier, quicker-to-update, data

    .. note::

        A smoothing factor of 1 would completely ignore history whereas 0 would
        completely ignore new data


    The initial value is the starting value for the EMA
    """
    def __init__(self, initial_value: float, smoothing_factor: float) -> None:
        self._value = initial_value
        if 0 < smoothing_factor < 1:
            self._alpha = smoothing_factor
        else:
            raise ValidationError("Smoothing factor of EMA must be between 0 and 1")

    def update(self, scalar: Union[int, float]) -> None:
        self._value = (self._value * (1 - self._alpha)) + (scalar * self._alpha)

    @property
    def value(self) -> float:
        return self._value
