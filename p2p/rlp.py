from eth_hash.auto import (
    keccak
)

import rlp
from rlp import sedes

from evm.rlp.headers import BlockHeader
from evm.rlp.transactions import BaseTransaction


# This is needed because BaseTransaction has several @abstractmethods, which means it can't be
# instantiated.
class P2PTransaction(rlp.Serializable):
    fields = BaseTransaction._meta.fields

    @property
    def hash(self) -> bytes:
        return keccak(rlp.encode(self))


class BlockBody(rlp.Serializable):
    fields = [
        ('transactions', sedes.CountableList(P2PTransaction)),
        ('uncles', sedes.CountableList(BlockHeader))
    ]
