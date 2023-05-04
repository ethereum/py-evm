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

from ..arrow_glacier import (
    ArrowGlacierBlock,
)
from ..arrow_glacier.blocks import (
    ArrowGlacierBlockHeader,
    ArrowGlacierMiningHeader,
)
from ..london.blocks import (
    LondonBackwardsHeader,
)
from .transactions import (
    GrayGlacierTransactionBuilder,
)


class GrayGlacierMiningHeader(ArrowGlacierMiningHeader, ABC):
    pass


class GrayGlacierBlockHeader(ArrowGlacierBlockHeader, ABC):
    def __str__(self) -> str:
        return f"<GrayGlacierBlockHeader #{self.block_number} {encode_hex(self.hash)[2:10]}>"  # noqa: E501


class GrayGlacierBlock(ArrowGlacierBlock):
    transaction_builder: Type[TransactionBuilderAPI] = GrayGlacierTransactionBuilder
    fields = [
        ("header", GrayGlacierBlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(LondonBackwardsHeader)),
    ]
