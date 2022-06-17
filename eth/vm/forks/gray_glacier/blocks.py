from abc import ABC
from typing import Type

from eth.abc import TransactionBuilderAPI
from eth_utils import (
    encode_hex,
)

from rlp.sedes import (
    CountableList,
)

from .transactions import (
    GrayGlacierTransactionBuilder,
)
from ..arrow_glacier import (
    ArrowGlacierBlock,
)
from ..arrow_glacier.blocks import (
    ArrowGlacierBlockHeader,
    ArrowGlacierMiningHeader,
)
from ..london.blocks import LondonBackwardsHeader


class GrayGlacierMiningHeader(ArrowGlacierMiningHeader, ABC):
    pass


class GrayGlacierBlockHeader(ArrowGlacierBlockHeader, ABC):
    def __str__(self) -> str:
        return f'<GrayGlacierBlockHeader #{self.block_number} {encode_hex(self.hash)[2:10]}>'


class GrayGlacierBlock(ArrowGlacierBlock):
    transaction_builder: Type[TransactionBuilderAPI] = GrayGlacierTransactionBuilder
    fields = [
        ('header', GrayGlacierBlockHeader),
        ('transactions', CountableList(transaction_builder)),
        ('uncles', CountableList(LondonBackwardsHeader))
    ]
