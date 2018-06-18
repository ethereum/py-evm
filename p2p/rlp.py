import rlp
from rlp import sedes


from evm.rlp.headers import BlockHeader
from evm.rlp.transactions import BaseTransactionFields


class BlockBody(rlp.Serializable):
    fields = [
        ('transactions', sedes.CountableList(BaseTransactionFields)),
        ('uncles', sedes.CountableList(BlockHeader))
    ]
