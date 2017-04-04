import rlp
from rlp.sedes import (
    CountableList,
)

from .headers import (
    BlockHeader,
)
from .transactions import (
    Transaction,
)


class Block(rlp.Serializable):
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(Transaction)),
        ('uncles', CountableList(BlockHeader))
    ]

    def __init__(self, header, transactions=None, uncles=None):
        if transactions is None:
            transactions = []
        if uncles is None:
            uncles = []
        super(Block, self).__init__(header=header, transactions=transactions, uncles=uncles)
