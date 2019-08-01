from rlp.sedes import (
    CountableList,
    binary,
)

from typing import (
    Tuple,
)

from eth.abc import LogAPI

from .sedes import (
    address,
    uint32,
)


class Log(LogAPI):
    fields = [
        ('address', address),
        ('topics', CountableList(uint32)),
        ('data', binary)
    ]

    def __init__(self, address: bytes, topics: Tuple[int, ...], data: bytes) -> None:
        super().__init__(address, topics, data)

    @property
    def bloomables(self) -> Tuple[bytes, ...]:
        return (
            self.address,
        ) + tuple(
            uint32.serialize(topic) for topic in self.topics
        )
