from enum import IntEnum, unique


@unique
class TickType(IntEnum):
    SLOT_START = 0
    SLOT_ONE_THIRD = 1  # SECONDS_PER_SLOT / 3
    SLOT_TWO_THIRD = 2  # SECONDS_PER_SLOT * 2 / 3

    @property
    def is_start(self) -> bool:
        return self == self.SLOT_START

    @property
    def is_one_third(self) -> bool:
        return self == self.SLOT_ONE_THIRD

    @property
    def is_two_third(self) -> bool:
        return self == self.SLOT_TWO_THIRD
