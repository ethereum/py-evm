from abc import ABC

from eth_utils import (
    encode_hex,
)

from rlp.sedes import (
    CountableList,
)
from eth.rlp.headers import (
    BlockHeader,
)

from .transactions import (
    ArrowGlacierTransactionBuilder,
)
from ..london import LondonBlock
from ..london.blocks import LondonBlockHeader, LondonMiningHeader


class ArrowGlacierMiningHeader(LondonMiningHeader, ABC):
    pass


class ArrowGlacierBlockHeader(LondonBlockHeader, ABC):
    def __str__(self) -> str:
        return f'<ArrowGlacierBlockHeader #{self.block_number} {encode_hex(self.hash)[2:10]}>'


class ArrowGlacierBlock(LondonBlock):
    transaction_builder = ArrowGlacierTransactionBuilder
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(transaction_builder)),
        ('uncles', CountableList(BlockHeader))
    ]
