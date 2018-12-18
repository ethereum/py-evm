from abc import ABC, abstractmethod
from typing import (
    Tuple,
    cast,
)

from eth_typing import BlockIdentifier, BlockNumber

from trinity._utils.headers import sequence_builder


class BaseHeaderRequest(ABC):
    block_number_or_hash: BlockIdentifier
    max_headers: int
    skip: int
    reverse: bool

    @property
    @abstractmethod
    def max_size(self) -> int:
        pass

    def generate_block_numbers(self, block_number: BlockNumber=None) -> Tuple[BlockNumber, ...]:
        if block_number is None and not self.is_numbered:
            raise TypeError(
                "A `block_number` must be supplied to generate block numbers "
                "for hash based header requests"
            )
        elif block_number is not None and self.is_numbered:
            raise TypeError(
                "The `block_number` parameter may not be used for number based "
                "header requests"
            )
        elif block_number is None:
            block_number = cast(BlockNumber, self.block_number_or_hash)

        max_headers = min(self.max_size, self.max_headers)

        return sequence_builder(
            block_number,
            max_headers,
            self.skip,
            self.reverse,
        )

    @property
    def is_numbered(self) -> bool:
        return isinstance(self.block_number_or_hash, int)
