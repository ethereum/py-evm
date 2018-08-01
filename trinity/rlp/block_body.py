import rlp
from rlp import sedes


from eth.rlp.headers import BlockHeader
from eth.rlp.transactions import BaseTransactionFields


class BlockBody(rlp.Serializable):
    fields = [
        ('transactions', sedes.CountableList(BaseTransactionFields)),
        ('uncles', sedes.CountableList(BlockHeader))
    ]
