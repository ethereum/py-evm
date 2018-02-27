import itertools

from rlp.sedes import (
    CountableList,
    binary,
)

from evm.rlp.headers import CollationHeader
from evm.rlp.collations import BaseCollation
from evm.rlp.receipts import Receipt

from evm.vm.forks.sharding.transactions import ShardingTransaction


class Collation(BaseCollation):
    transaction_class = ShardingTransaction
    fields = [
        ('header', CollationHeader),
        ('transactions', CountableList(transaction_class)),
        ('witness_nodes', CountableList(binary))
    ]

    def __init__(self, header, transactions=None, witness_nodes=None):
        if transactions is None:
            transactions = []
        if witness_nodes is None:
            witness_nodes = []

        self.transaction_fee_sum = 0

        super(Collation, self).__init__(
            header=header,
            transactions=transactions,
            witness_nodes=witness_nodes,
        )

    #
    # Helpers
    #
    @property
    def shard_id(self):
        return self.header.shard_id

    @property
    def expected_period_number(self):
        return self.header.expected_period_number

    @property
    def number(self):
        return self.header.number

    @property
    def hash(self):
        return self.header.hash

    #
    # Transaction class for this block class
    #
    @classmethod
    def get_transaction_class(cls):
        return cls.transaction_class

    #
    # Receipts API
    #
    def get_receipts(self, chaindb):
        return chaindb.get_receipts(self.header, Receipt)

    #
    # Header API
    #
    @classmethod
    def from_header(cls, header, chaindb):
        """
        Returns the collation denoted by the given collation header.
        """
        transactions = chaindb.get_block_transactions(header, cls.get_transaction_class())
        prefixes_nested = [transaction.prefix_list for transaction in transactions]
        prefixes = itertools.chain.from_iterable(prefixes_nested)
        witness_node_set = chaindb.get_witness_nodes(header, prefixes)
        witness_nodes = sorted(list(witness_node_set))

        return cls(
            header=header,
            transactions=transactions,
            witness_nodes=witness_nodes,
        )
