import rlp
from rlp import sedes

from evm.rlp.headers import BlockHeader
from evm.rlp.transactions import BaseTransaction


# This is needed because BaseTransaction has several @abstractmethods, which means it can't be
# instantiated.
class P2PTransaction(rlp.Serializable):
    fields = BaseTransaction._meta.fields


class BlockBody(rlp.Serializable):
    fields = [
        ('transactions', sedes.CountableList(P2PTransaction)),
        ('uncles', sedes.CountableList(BlockHeader))
    ]
