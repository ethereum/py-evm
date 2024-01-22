from abc import (
    ABC,
)
from typing import (
    Type,
)

from eth_typing import (
    Hash32,
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
from eth.vm.forks.gray_glacier.blocks import (
    GrayGlacierBlock,
    GrayGlacierBlockHeader,
)

from ..london.blocks import (
    LondonBackwardsHeader,
)
from .transactions import (
    ParisTransactionBuilder,
)


class ParisBlockHeader(GrayGlacierBlockHeader, ABC):
    def __str__(self) -> str:
        return f"<ParisBlockHeader #{self.block_number} {encode_hex(self.hash)[2:10]}>"

    @property
    def mining_hash(self) -> Hash32:
        raise ValueError("Mining hash is not available post merge.")


class ParisBlock(GrayGlacierBlock):
    transaction_builder: Type[TransactionBuilderAPI] = ParisTransactionBuilder
    fields = [
        ("header", ParisBlockHeader),
        ("transactions", CountableList(transaction_builder)),
        # no uncles in pos, max_length=0
        ("uncles", CountableList(LondonBackwardsHeader, max_length=0)),
    ]
