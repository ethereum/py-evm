import rlp
from rlp.sedes import CountableList

from evm.exceptions import ValidationError
from evm.rlp.headers import CollationHeader
from evm.rlp.collations import BaseCollation

from .transactions import ShardingTransaction


class Collation(BaseCollation):
    transaction_class = ShardingTransaction
    fields = [
        ('header', CollationHeader),
        ('transactions', CountableList(transaction_class))
    ]

    chaindb = None

    def __init__(self, header, chaindb, transactions):
        self.chaindb = chaindb

        if transactions is None:
            transactions = []

        super(Collation, self).__init__(
            header=header,
            transactions=transactions
        )

    def validate(self):
        if not self.chaindb.exists(self.header.state_root):
            raise ValidationError(
                "`state_root` was not found in the db.\n"
                "- state_root: {0}".format(
                    self.header.state_root,
                )
            )

    #
    # Helpers
    #
    @property
    def number(self):
        return self.header.number

    @property
    def hash(self):
        return self.header.hash

    def get_parent_header(self):
        return self.chaindb.get_collation_header_by_hash(self.header.parent_collation_hash)

    #
    # Transaction class for this block class
    #
    @classmethod
    def get_transaction_class(cls):
        return cls.transaction_class

    #
    # Gas Usage API
    #
    # TODO

    #
    # Receipts API
    #
    # TODO

    #
    # Header API
    #
    @classmethod
    def from_header(cls, header, chaindb):
        """
        Returns the collation denoted by the given collation header.
        """
        transactions = chaindb.get_collation_transactions(header, cls.get_transaction_class())

        return cls(
            header=header,
            transactions=transactions,
            chaindb=chaindb,
        )

    #
    # Execution API
    #
    def add_transaction(self, transaction, computation):
        transaction_idx = len(self.transactions)
        index_key = rlp.encode(transaction_idx, sedes=rlp.sedes.big_endian_int)

        self.transactions.append(transaction)

        tx_root_hash = self.chaindb.add_transaction(self.header, index_key, transaction)

        self.header.transaction_root = tx_root_hash

        return self
