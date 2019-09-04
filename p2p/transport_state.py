import enum


@enum.unique
class TransportState(enum.Enum):
    IDLE = enum.auto()
    HEADER = enum.auto()
    BODY = enum.auto()
