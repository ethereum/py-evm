import rlp
from rlp.sedes import (
    CountableList,
)

from trie import (
    Trie,
)

from evm.state import (
    State,
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

    def __init__(self, header, transactions=None, uncles=None, db=None):
        if transactions is None:
            transactions = []
        if uncles is None:
            uncles = []

        self.db = db

        if self.db is None:
            raise TypeError("Block must have a db")

        super(Block, self).__init__(header=header, transactions=transactions, uncles=uncles)

        self.state_db = State(self.db, root_hash=self.header.state_root)
        self.transaction_db = Trie(self.db, root_hash=self.header.transaction_root)
        self.receipt_db = Trie(self.db, root_hash=self.header.receipts_root)
