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
    ParisTransactionBuilder,
)
from eth.vm.forks.paris.blocks import (
    ParisBlock,
    ParisBlockHeader,
    ParisMiningHeader,
)
from ..london.blocks import (
    LondonBackwardsHeader,
)


class ShanghaiMiningHeader(ParisMiningHeader, ABC):
    pass


class ShanghaiBlockHeader(ParisBlockHeader, ABC):
    def __str__(self) -> str:
        return f'<ShanghaiBlockHeader #{self.block_number} {encode_hex(self.hash)[2:10]}>'


class ShanghaiBlock(ParisBlock):
    transaction_builder: Type[TransactionBuilderAPI] = ParisTransactionBuilder
    fields = [
        ('header', ShanghaiBlockHeader),
        ('transactions', CountableList(transaction_builder)),
        ('uncles', CountableList(LondonBackwardsHeader, max_length=0)),
    ]
