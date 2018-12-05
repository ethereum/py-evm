import itertools

import rlp
from rlp.sedes import (
    big_endian_int,
    CountableList,
    binary,
)

from eth_bloom import BloomFilter

from .sedes import (
    uint256,
)

from .logs import Log

from typing import Iterable


class Receipt(rlp.Serializable):

    fields = [
        ('state_root', binary),
        ('gas_used', big_endian_int),
        ('bloom', uint256),
        ('logs', CountableList(Log))
    ]

    def __init__(self,
                 state_root: bytes,
                 gas_used: int,
                 logs: Iterable[Log],
                 bloom: int=None) -> None:

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

    @bloom_filter.setter
    def bloom_filter(self, value: BloomFilter) -> None:
        self.bloom = int(value)
