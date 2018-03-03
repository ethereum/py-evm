from __future__ import absolute_import

import contextlib
import logging
import rlp

from eth_utils import (
    keccak,
    to_tuple,
)

from evm.constants import (
    GENESIS_PARENT_HASH,
    MAX_PREV_HEADER_DEPTH,
    MAX_UNCLES,
)
from evm.exceptions import (
    BlockNotFound,
    ValidationError,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.utils.datatypes import (
    Configurable,
)
from evm.utils.db import (
    get_parent_header,
    get_block_header_by_hash,
)
from evm.utils.headers import (
    generate_header_from_parent_header,
)
from evm.validation import (
    validate_length_lte,
    validate_gas_limit,
)
from evm.vm.message import (
    Message,
)


class BaseVM(Configurable):
    """
    The VM class represents the Chain rules for a specific protocol definition
    such as the Frontier or Homestead network.  Define a Chain which specifies
    the individual VM classes for each fork of the protocol rules within that
    network.
    """
    chaindb = None
    _block_class = None
    _state_class = None

    def __init__(self, header, chaindb):
        self.chaindb = chaindb
        block_class = self.get_block_class()
        self.block = block_class.from_header(header=header, chaindb=self.chaindb)

    #
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('evm.vm.base.VM.{0}'.format(self.__class__.__name__))

    #
    # Execution
    #
    def apply_transaction(self, transaction):
        """
        Apply the transaction to the vm in the current block.
        """
        computation, block, trie_data_dict = self.get_state_class().apply_transaction(
            self.state,
            transaction,
            self.block,
        )
        self.block = block

        # Persist changed transaction and receipt key-values to self.chaindb.
        self.chaindb.persist_trie_data_dict(trie_data_dict)

        self.clear_journal()

        return computation, self.block

    def execute_bytecode(self,
                         origin,
                         gas_price,
                         gas,
                         to,
                         sender,
                         value,
                         data,
                         code,
                         code_address=None,
                         ):
        if origin is None:
            origin = sender

        # Construct a message
        message = Message(
            gas=gas,
            to=to,
            sender=sender,
            value=value,
            data=data,
            code=code,
            code_address=code_address,
        )

        # Construction a tx context
        transaction_context = self.state.get_transaction_context_class()(
            gas_price=gas_price,
            origin=origin,
        )

        # Execute it in the VM
        return self.state.get_computation(message, transaction_context).apply_computation(
            self.state,
            message,
            transaction_context,
        )

    #
    # Mining
    #
    def import_block(self, block):
        self.configure_header(
            coinbase=block.header.coinbase,
            gas_limit=block.header.gas_limit,
            timestamp=block.header.timestamp,
            extra_data=block.header.extra_data,
            mix_hash=block.header.mix_hash,
            nonce=block.header.nonce,
            uncles_hash=keccak(rlp.encode(block.uncles)),
        )

        # run all of the transactions.
        for transaction in block.transactions:
            self.apply_transaction(transaction)

        # transfer the list of uncles.
        self.block.uncles = block.uncles

        return self.mine_block()

    def mine_block(self, *args, **kwargs):
        """
        Mine the current block. Proxies to self.pack_block method.
        """
        block = self.block
        self.pack_block(block, *args, **kwargs)

        if block.number == 0:
            return block

        block = self.state.finalize_block(block)

        return block

    def pack_block(self, block, *args, **kwargs):
        """
        Pack block for mining.

        :param bytes coinbase: 20-byte public address to receive block reward
        :param bytes uncles_hash: 32 bytes
        :param bytes state_root: 32 bytes
        :param bytes transaction_root: 32 bytes
        :param bytes receipt_root: 32 bytes
        :param int bloom:
        :param int gas_used:
        :param bytes extra_data: 32 bytes
        :param bytes mix_hash: 32 bytes
        :param bytes nonce: 8 bytes
        """
        if 'uncles' in kwargs:
            block.uncles = kwargs.pop('uncles')
            kwargs.setdefault('uncles_hash', keccak(rlp.encode(block.uncles)))

        header = block.header
        provided_fields = set(kwargs.keys())
        known_fields = set(tuple(zip(*BlockHeader.fields))[0])
        unknown_fields = provided_fields.difference(known_fields)

        if unknown_fields:
            raise AttributeError(
                "Unable to set the field(s) {0} on the `BlockHeader` class. "
                "Received the following unexpected fields: {1}.".format(
                    ", ".join(known_fields),
                    ", ".join(unknown_fields),
                )
            )

        for key, value in kwargs.items():
            setattr(header, key, value)

        # Perform validation
        self.validate_block(block)

        return block

    @contextlib.contextmanager
    def state_in_temp_block(self):
        header = self.block.header
        temp_block = self.generate_block_from_parent_header_and_coinbase(header, header.coinbase)
        prev_hashes = (header.hash, ) + self.previous_hashes
        state = self.get_state(block_header=temp_block.header, prev_hashes=prev_hashes)
        snapshot = state.snapshot()
        yield state
        state.revert(snapshot)

    @classmethod
    def generate_block_from_parent_header_and_coinbase(cls, parent_header, coinbase):
        """
        Generate block from parent header and coinbase.
        """
        block_header = generate_header_from_parent_header(
            cls.compute_difficulty,
            parent_header,
            coinbase,
            timestamp=parent_header.timestamp + 1,
        )
        block = cls.get_block_class()(
            block_header,
            transactions=[],
            uncles=[],
        )
        return block

    #
    # Validate
    #
    def validate_block(self, block):
        if not block.is_genesis:
            parent_header = get_parent_header(block.header, self.chaindb)

            validate_gas_limit(block.header.gas_limit, parent_header.gas_limit)
            validate_length_lte(block.header.extra_data, 32, title="BlockHeader.extra_data")

            # timestamp
            if block.header.timestamp < parent_header.timestamp:
                raise ValidationError(
                    "`timestamp` is before the parent block's timestamp.\n"
                    "- block  : {0}\n"
                    "- parent : {1}. ".format(
                        block.header.timestamp,
                        parent_header.timestamp,
                    )
                )
            elif block.header.timestamp == parent_header.timestamp:
                raise ValidationError(
                    "`timestamp` is equal to the parent block's timestamp\n"
                    "- block : {0}\n"
                    "- parent: {1}. ".format(
                        block.header.timestamp,
                        parent_header.timestamp,
                    )
                )

        if len(block.uncles) > MAX_UNCLES:
            raise ValidationError(
                "Blocks may have a maximum of {0} uncles.  Found "
                "{1}.".format(MAX_UNCLES, len(block.uncles))
            )

        for uncle in block.uncles:
            self.validate_uncle(block, uncle)

        if not self.state.is_key_exists(block.header.state_root):
            raise ValidationError(
                "`state_root` was not found in the db.\n"
                "- state_root: {0}".format(
                    block.header.state_root,
                )
            )
        local_uncle_hash = keccak(rlp.encode(block.uncles))
        if local_uncle_hash != block.header.uncles_hash:
            raise ValidationError(
                "`uncles_hash` and block `uncles` do not match.\n"
                " - num_uncles       : {0}\n"
                " - block uncle_hash : {1}\n"
                " - header uncle_hash: {2}".format(
                    len(block.uncles),
                    local_uncle_hash,
                    block.header.uncle_hash,
                )
            )

    def validate_uncle(self, block, uncle):
        if uncle.block_number >= block.number:
            raise ValidationError(
                "Uncle number ({0}) is higher than block number ({1})".format(
                    uncle.block_number, block.number))
        try:
            parent_header = get_block_header_by_hash(uncle.parent_hash, self.chaindb)
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
    # Transactions
    #

    @classmethod
    def get_transaction_class(cls):
        """
        Return the class that this VM uses for transactions.
        """
        return cls.get_block_class().get_transaction_class()

    def get_pending_transaction(self, transaction_hash):
        return self.chaindb.get_pending_transaction(transaction_hash, self.get_transaction_class())

    def create_transaction(self, *args, **kwargs):
        """
        Proxy for instantiating a transaction for this VM.
        """
        return self.get_transaction_class()(*args, **kwargs)

    def create_unsigned_transaction(self, *args, **kwargs):
        """
        Proxy for instantiating a transaction for this VM.
        """
        return self.get_transaction_class().create_unsigned_transaction(*args, **kwargs)

    #
    # Blocks
    #
    @classmethod
    def get_block_class(cls):
        """
        Return the class that this VM uses for blocks.
        """
        if cls._block_class is None:
            raise AttributeError("No `_block_class` has been set for this VM")

        return cls._block_class

    @classmethod
    def get_block_by_header(cls, block_header, db):
        return cls.get_block_class().from_header(block_header, db)

    @classmethod
    @to_tuple
    def get_prev_hashes(cls, last_block_hash, db):
        if last_block_hash == GENESIS_PARENT_HASH:
            return

        block_header = get_block_header_by_hash(last_block_hash, db)

        for _ in range(MAX_PREV_HEADER_DEPTH):
            yield block_header.hash
            try:
                block_header = get_parent_header(block_header, db)
            except (IndexError, BlockNotFound):
                break

    @property
    def previous_hashes(self):
        return self.get_prev_hashes(self.block.header.parent_hash, self.chaindb)

    #
    # Gas Usage API
    #
    def get_cumulative_gas_used(self, block):
        """
        Note return value of this function can be cached based on
        `self.receipt_db.root_hash`
        """
        if len(block.transactions):
            return block.get_receipts(self.chaindb)[-1].gas_used
        else:
            return 0

    #
    # Headers
    #
    @classmethod
    def create_header_from_parent(cls, parent_header, **header_params):
        """
        Creates and initializes a new block header from the provided
        `parent_header`.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def configure_header(self, **header_params):
        """
        Setup the current header with the provided parameters.  This can be
        used to set fields like the gas limit or timestamp to value different
        than their computed defaults.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    def compute_difficulty(cls, parent_header, timestamp):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Snapshot and Revert
    #
    def clear_journal(self):
        """
        Clear the journal.  This should be called at any point of VM execution
        where the statedb is being committed, such as after a transaction has
        been applied to a block.
        """
        self.chaindb.clear()

    #
    # State
    #
    @classmethod
    def get_state_class(cls):
        """
        Return the class that this VM uses for states.
        """
        if cls._state_class is None:
            raise AttributeError("No `_state_class` has been set for this VM")

        return cls._state_class

    def get_state(self, chaindb=None, block_header=None, prev_hashes=None):
        """Return state object
        """
        if chaindb is None:
            chaindb = self.chaindb
        if block_header is None:
            block_header = self.block.header
        if prev_hashes is None:
            prev_hashes = self.get_prev_hashes(
                last_block_hash=block_header.parent_hash,
                db=chaindb,
            )

        execution_context = block_header.create_execution_context(prev_hashes)
        receipts = self.block.get_receipts(self.chaindb)
        return self.get_state_class()(
            chaindb,
            execution_context=execution_context,
            state_root=block_header.state_root,
            receipts=receipts,
        )

    @property
    def state(self):
        """Return current state property
        """
        return self.get_state(
            chaindb=self.chaindb,
            block_header=self.block.header,
        )
