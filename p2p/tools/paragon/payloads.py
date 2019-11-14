from typing import NamedTuple


class BroadcastDataPayload(NamedTuple):
    data: bytes


class GetSumPayload(NamedTuple):
    a: int
    b: int


class SumPayload(NamedTuple):
    c: int
