import rlp
from rlp.sedes import (
    CountableList,
)

from eth_bloom import (
    BloomFilter,
)

from evm.constants import (
    EMPTY_UNCLE_HASH,
    GAS_LIMIT_ADJUSTMENT_FACTOR,
    GAS_LIMIT_MAXIMUM,
    GAS_LIMIT_MINIMUM,
    MAX_UNCLES,
)
from evm.exceptions import (
    BlockNotFound,
    ValidationError,
)
from evm.rlp.logs import (
    Log,
)
from evm.rlp.receipts import (
    Receipt,
)
from evm.rlp.blocks import (
    BaseBlock,
)
from evm.rlp.headers import (
    BlockHeader,
)

from evm.utils.keccak import (
    keccak,
)
from evm.validation import (
    validate_length_lte,
)

from .transactions import (
    FrontierTransaction,
)


class FrontierBlock(BaseBlock):
    transaction_class = FrontierTransaction
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(transaction_class)),
        ('uncles', CountableList(BlockHeader))
    ]

    chaindb = None
    bloom_filter = None

    def __init__(self, header, chaindb, transactions=None, uncles=None):
        self.chaindb = chaindb

        if transactions is None:
            transactions = []
        if uncles is None:
            uncles = []

        self.bloom_filter = BloomFilter(header.bloom)

        super(FrontierBlock, self).__init__(
            header=header,
            transactions=transactions,
            uncles=uncles,
        )
        # TODO: should perform block validation at this point?

    def validate_gas_limit(self):
        gas_limit = self.header.gas_limit
        if gas_limit < GAS_LIMIT_MINIMUM:
            raise ValidationError("Gas limit {0} is below minimum {1}".format(
                gas_limit, GAS_LIMIT_MINIMUM))
        if gas_limit > GAS_LIMIT_MAXIMUM:
            raise ValidationError("Gas limit {0} is above maximum {1}".format(
                gas_limit, GAS_LIMIT_MAXIMUM))
        parent_gas_limit = self.get_parent_header().gas_limit
        diff = gas_limit - parent_gas_limit
        if diff > (parent_gas_limit // GAS_LIMIT_ADJUSTMENT_FACTOR):
            raise ValidationError(
                "Gas limit {0} difference to parent {1} is too big {2}".format(
                    gas_limit, parent_gas_limit, diff))

    def validate(self):
        if not self.is_genesis:
            parent_header = self.get_parent_header()

            self.validate_gas_limit()
            validate_length_lte(self.header.extra_data, 32, title="BlockHeader.extra_data")

            # timestamp
            if self.header.timestamp < parent_header.timestamp:
                raise ValidationError(
                    "`timestamp` is before the parent block's timestamp.\n"
                    "- block  : {0}\n"
                    "- parent : {1}. ".format(
                        self.header.timestamp,
                        parent_header.timestamp,
                    )
                )
            elif self.header.timestamp == parent_header.timestamp:
                raise ValidationError(
                    "`timestamp` is equal to the parent block's timestamp\n"
                    "- block : {0}\n"
                    "- parent: {1}. ".format(
                        self.header.timestamp,
                        parent_header.timestamp,
                    )
                )

        # XXX: Should these and some other checks be moved into
        # VM.validate_block(), as they apply to all block flavours?
        if len(self.uncles) > MAX_UNCLES:
            raise ValidationError(
                "Blocks may have a maximum of {0} uncles.  Found "
                "{1}.".format(MAX_UNCLES, len(self.uncles))
            )

        for uncle in self.uncles:
            self.validate_uncle(uncle)

        if not self.chaindb.exists(self.header.state_root):
            raise ValidationError(
                "`state_root` was not found in the db.\n"
                "- state_root: {0}".format(
                    self.header.state_root,
                )
            )
        local_uncle_hash = keccak(rlp.encode(self.uncles))
        if local_uncle_hash != self.header.uncles_hash:
            raise ValidationError(
                "`uncles_hash` and block `uncles` do not match.\n"
                " - num_uncles       : {0}\n"
                " - block uncle_hash : {1}\n"
                " - header uncle_hash: {2}".format(
                    len(self.uncles),
                    local_uncle_hash,
                    self.header.uncle_hash,
                )
            )

        super(FrontierBlock, self).validate()

    def validate_uncle(self, uncle):
        if uncle.block_number >= self.number:
            raise ValidationError(
                "Uncle number ({0}) is higher than block number ({1})".format(
                    uncle.block_number, self.number))
        try:
            parent_header = self.chaindb.get_block_header_by_hash(uncle.parent_hash)
        except BlockNotFound:
            raise ValidationError(
                "Uncle ancestor not found: {0}".format(uncle.parent_hash))
        if uncle.block_number != parent_header.block_number + 1:
            raise ValidationError(
                "Uncle number ({0}) is not one above ancestor's number ({1})".format(
                    uncle.block_number, parent_header.block_number))
        if uncle.timestamp < parent_header.timestamp:
            raise ValidationError(
                "Uncle timestamp ({0}) is before ancestor's timestamp ({1})".format(
                    uncle.timestamp, parent_header.timestamp))
        if uncle.gas_used > uncle.gas_limit:
            raise ValidationError(
                "Uncle's gas usage ({0}) is above the limit ({1})".format(
                    uncle.gas_used, uncle.gas_limit))

    #
    # Helpers
    #
    @property
    def number(self):
        return self.header.block_number

    @property
    def hash(self):
        return self.header.hash

    def get_parent_header(self):
        return self.chaindb.get_block_header_by_hash(self.header.parent_hash)

    #
    # Transaction class for this block class
    #
    @classmethod
    def get_transaction_class(cls):
        return cls.transaction_class

    #
    # Gas Usage API
    #
    def get_cumulative_gas_used(self):
        """
        Note return value of this function can be cached based on
        `self.receipt_db.root_hash`
        """
        if len(self.transactions):
            return self.receipts[-1].gas_used
        else:
            return 0

    #
    # Receipts API
    #
    @property
    def receipts(self):
        return self.chaindb.get_receipts(self.header, Receipt)

    def make_receipt(self, transaction, computation):
        logs = [
            Log(address, topics, data)
            for address, topics, data
            in computation.get_log_entries()
        ]

        gas_remaining = computation.get_gas_remaining()
        gas_refund = computation.get_gas_refund()
        tx_gas_used = (
            transaction.gas - gas_remaining
        ) - min(
            gas_refund,
            (transaction.gas - gas_remaining) // 2,
        )

        gas_used = self.header.gas_used + tx_gas_used

        receipt = Receipt(
            state_root=self.header.state_root,
            gas_used=gas_used,
            logs=logs,
        )
        return receipt

    #
    # Header API
    #
    @classmethod
    def from_header(cls, header, chaindb):
        """
        Returns the block denoted by the given block header.
        """
        if header.uncles_hash == EMPTY_UNCLE_HASH:
            uncles = []
        else:
            uncles = chaindb.get_block_uncles(header.uncles_hash)

        transactions = chaindb.get_block_transactions(header, cls.get_transaction_class())

        return cls(
            header=header,
            transactions=transactions,
            uncles=uncles,
            chaindb=chaindb,
        )

    #
    # Execution API
    #
    def add_transaction(self, transaction, computation):
        receipt = self.make_receipt(transaction, computation)

        transaction_idx = len(self.transactions)

        index_key = rlp.encode(transaction_idx, sedes=rlp.sedes.big_endian_int)

        self.transactions.append(transaction)

        tx_root_hash = self.chaindb.add_transaction(self.header, index_key, transaction)
        receipt_root_hash = self.chaindb.add_receipt(self.header, index_key, receipt)

        self.bloom_filter |= receipt.bloom

        self.header.transaction_root = tx_root_hash
        self.header.receipt_root = receipt_root_hash
        self.header.bloom = int(self.bloom_filter)
        self.header.gas_used = receipt.gas_used

        return self

    def add_uncle(self, uncle):
        self.uncles.append(uncle)
        self.header.uncles_hash = keccak(rlp.encode(self.uncles))
        return self

    def mine(self, **kwargs):
        """
        - `coinbase`
        - `uncles_hash`
        - `state_root`
        - `transaction_root`
        - `receipt_root`
        - `bloom`
        - `gas_used`
        - `extra_data`
        - `mix_hash`
        - `nonce`
        """
        if 'uncles' in kwargs:
            self.uncles = kwargs.pop('uncles')
            kwargs.setdefault('uncles_hash', keccak(rlp.encode(self.uncles)))

        header = self.header
        provided_fields = set(kwargs.keys())
        known_fields = set(tuple(zip(*BlockHeader.fields))[0])
        unknown_fields = provided_fields.difference(known_fields)

        if unknown_fields:
            raise AttributeError(
                "Unable to set the field(s) {0} on the `BlockHeader` class. "
                "Received the following unexpected fields: {0}.".format(
                    ", ".join(known_fields),
                    ", ".join(unknown_fields),
                )
            )

        for key, value in kwargs.items():
            setattr(header, key, value)

        # Perform validation
        self.validate()

        return self
