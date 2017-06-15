import rlp
from rlp.sedes import (
    CountableList,
)

from eth_bloom import (
    BloomFilter,
)

from trie import (
    Trie,
)

from evm.constants import (
    GAS_LIMIT_EMA_DENOMINATOR,
    GAS_LIMIT_ADJUSTMENT_FACTOR,
    GAS_LIMIT_MINIMUM,
    GAS_LIMIT_USAGE_ADJUSTMENT_NUMERATOR,
    GAS_LIMIT_USAGE_ADJUSTMENT_DENOMINATOR,
)
from evm.state import (
    State,
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

from evm.utils.transactions import (
    get_transactions_from_db,
)
from evm.utils.receipts import (
    get_receipts_from_db,
)

from .transactions import (
    FrontierTransaction,
)


def compute_gas_limit_bounds(parent):
    boundary_range = parent.gas_limit // GAS_LIMIT_ADJUSTMENT_FACTOR
    upper_bound = parent.gas_limit + boundary_range
    lower_bound = max(GAS_LIMIT_MINIMUM, parent.gas_limit - boundary_range)
    return lower_bound, upper_bound


def compute_adjusted_gas_limit(parent_header, gas_limit_floor):
    """
    A simple strategy for adjusting the gas limit.

    For each block:

    - decrease by 1/1024th of the gas limit from the previous block
    - increase by 50% of the total gas used by the previous block

    If the value is less than the given `gas_limit_floor`:

    - increase the gas limit by 1/1024th of the gas limit from the previous block.

    If the value is less than the GAS_LIMIT_MINIMUM:

    - use the GAS_LIMIT_MINIMUM as the new gas limit.
    """
    if gas_limit_floor < GAS_LIMIT_MINIMUM:
        raise ValueError(
            "The `gas_limit_floor` value must be greater than the "
            "GAS_LIMIT_MINIMUM.  Got {0}.  Must be greater than "
            "{1}".format(gas_limit_floor, GAS_LIMIT_MINIMUM)
        )

    decay = parent_header.gas_limit // GAS_LIMIT_EMA_DENOMINATOR

    if parent_header.gas_used:
        usage_increase = (
            parent_header.gas_used * GAS_LIMIT_USAGE_ADJUSTMENT_NUMERATOR
        ) // (
            GAS_LIMIT_USAGE_ADJUSTMENT_DENOMINATOR
        ) // (
            GAS_LIMIT_EMA_DENOMINATOR
        )
    else:
        usage_increase = 0

    gas_limit = max(
        GAS_LIMIT_MINIMUM,
        parent_header.gas_limit - decay + usage_increase
    )

    if gas_limit < gas_limit_floor:
        return GAS_LIMIT_MINIMUM
    else:
        return gas_limit


class FrontierBlock(BaseBlock):
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(FrontierTransaction)),
        ('uncles', CountableList(BlockHeader))
    ]

    db = None
    bloom_filter = None

    def __init__(self, header, transactions=[], uncles=[], db=None):
        if db is not None:
            self.db = db

        if self.db is None:
            raise TypeError("Block must have a db")

        self.bloom_filter = BloomFilter(header.bloom)
        self.state_db = State(db=db, root_hash=header.state_root)
        self.transaction_db = Trie(db=db, root_hash=header.transaction_root)
        self.receipt_db = Trie(db=db, root_hash=header.receipt_root)

        super(FrontierBlock, self).__init__(
            header=header,
            transactions=transactions,
            uncles=uncles,
        )
        # TODO: should perform block validation at this point?

    #
    # Transaction class for this block class
    #
    transaction_class = FrontierTransaction

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
        return get_receipts_from_db(self.receipt_db, Receipt)

    #
    # Header API
    #
    @classmethod
    def from_header(cls, header):
        """
        Update this block to the values represented by the given header.
        """
        uncles = rlp.decode(cls.db.get(header.uncles_hash), sedes=CountableList(BlockHeader))

        transaction_db = Trie(cls.db, root_hash=header.transaction_root)
        transactions = get_transactions_from_db(transaction_db, cls.get_transaction_class())

        return cls(
            header=header,
            transactions=transactions,
            uncles=uncles,
        )

    #
    # Execution API
    #
    def apply_transaction(self, evm, transaction):
        init_state_root = evm.block.state_db.root_hash
        computation = evm.apply_transaction(transaction)

        logs = [
            Log(address, topics, data)
            for address, topics, data
            in computation.get_log_entries()
        ]
        receipt = Receipt(
            state_root=evm.block.state_db.root_hash,
            gas_used=transaction.get_intrensic_gas() + computation.get_gas_used(),
            logs=logs,
        )

        transaction_idx = len(self.transactions)
        transaction_key = rlp.encode(transaction_idx)

        self.transactions.append(transaction)
        self.transaction_db[transaction_key] = rlp.encode(transaction)

        self.receipt_db[transaction_key] = rlp.encode(receipt)
        self.bloom_filter |= receipt.bloom

        self.header.transaction_root = self.transaction_db.root_hash
        self.header.state_root = evm.block.state_db.root_hash
        self.header.receipt_root = self.receipt_db.root_hash
        self.header.bloom = int(self.bloom_filter)
        self.header.gas_used = self.get_cumulative_gas_used()

        if evm.block.state_db.root_hash == init_state_root:
            assert False

        return computation

    def mine(self, **kwargs):
        """
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
        header = self.header
        provided_fields = set(kwargs.keys())
        known_fields = set(tuple(zip(*BlockHeader.fields))[0])
        unknown_fields = provided_fields.difference(known_fields)

        if unknown_fields:
            raise AttributeError(
                "Unable to set the field(s) {0} on the `BlockHeader` class. "
                "Received the following unexpected fields: {0}.".format(
                    ", ".join(unknown_fields),
                    ", ".join(known_fields),
                )
            )

        for key, value in kwargs.items():
            setattr(header, key, value)

        # TODO: do we validate here!?
        return self
