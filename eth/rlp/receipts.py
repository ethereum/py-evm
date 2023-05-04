import itertools
from typing import (
    Iterable,
)

from eth_bloom import (
    BloomFilter,
)
import rlp
from rlp.sedes import (
    CountableList,
    big_endian_int,
    binary,
)

from eth.abc import (
    ReceiptAPI,
    ReceiptBuilderAPI,
)

from .logs import (
    Log,
)
from .sedes import (
    uint256,
)


class Receipt(rlp.Serializable, ReceiptAPI, ReceiptBuilderAPI):
    type_id = None

    fields = [
        ("state_root", binary),
        ("gas_used", big_endian_int),
        ("bloom", uint256),
        ("logs", CountableList(Log)),
    ]

    def __init__(
        self, state_root: bytes, gas_used: int, logs: Iterable[Log], bloom: int = None
    ) -> None:
        if bloom is None:
            bloomables = itertools.chain.from_iterable(log.bloomables for log in logs)
            bloom = int(BloomFilter.from_iterable(bloomables))

        super().__init__(
            state_root=state_root,
            gas_used=gas_used,
            bloom=bloom,
            logs=logs,
        )

    @property
    def bloom_filter(self) -> BloomFilter:
        return BloomFilter(self.bloom)

    @classmethod
    def decode(cls, encoded: bytes) -> ReceiptAPI:
        return rlp.decode(encoded, sedes=cls)

    def encode(self) -> bytes:
        return rlp.encode(self)
