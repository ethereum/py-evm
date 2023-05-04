from abc import (
    ABC,
)
from typing import (
    Type,
)

from eth_utils import (
    encode_hex,
)
from rlp.sedes import (
    CountableList,
)

from eth.abc import (
    TransactionBuilderAPI,
)

from ..london import (
    LondonBlock,
)
from ..london.blocks import (
    LondonBackwardsHeader,
    LondonBlockHeader,
    LondonMiningHeader,
)
from .transactions import (
    ArrowGlacierTransactionBuilder,
)


class ArrowGlacierMiningHeader(LondonMiningHeader, ABC):
    pass


class ArrowGlacierBlockHeader(LondonBlockHeader, ABC):
    def __str__(self) -> str:
        return f"<ArrowGlacierBlockHeader #{self.block_number} {encode_hex(self.hash)[2:10]}>"  # noqa: E501


class ArrowGlacierBlock(LondonBlock):
    transaction_builder: Type[TransactionBuilderAPI] = ArrowGlacierTransactionBuilder
    fields = [
        ("header", ArrowGlacierBlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(LondonBackwardsHeader)),
    ]
