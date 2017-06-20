from __future__ import absolute_import

import logging
import time

import rlp

from evm.constants import (
    BLOCK_REWARD,
    NEPHEW_REWARD,
    UNCLE_DEPTH_PENALTY_FACTOR,
)
from evm.logic.invalid import (
    InvalidOpcode,
)
from evm.exceptions import (
    ValidationError,
)
from evm.validation import (
    validate_evm_block_ranges,
)

from evm.rlp.headers import (
    BlockHeader,
)

from evm.utils.db import (
    make_block_number_to_hash_lookup_key,
    make_block_hash_to_number_lookup_key,
)
from evm.utils.blocks import (
    persist_block_to_db,
)
from evm.utils.ranges import (
    range_sort_fn,
    find_range,
)

from evm.state import State


class BaseEVM(object):
    """
    The EVM class is... TODO:
    """
    db = None

    block = None

    opcodes = None
    block_class = None

    def __init__(self, header, db=None):
        if db is not None:
            self.db = db

        if self.db is None:
            raise ValueError("EVM classes must have a `db`")

        self.header = header

        block_class = self.get_block_class()
        self.block = block_class.from_header(header=self.header)
        self.state_db = State(db=self.db, root_hash=self.header.state_root)

    @classmethod
    def configure(cls,
                  name=None,
                  **overrides):
        if name is None:
            name = cls.__name__

        for key in overrides:
            if not hasattr(cls, key):
                raise TypeError(
                    "The EVM.configure cannot set attributes that are not "
                    "already present on the base class.  The attribute `{0}` was "
                    "not found on the base class `{1}`".format(key, cls)
                )
        return type(name, (cls,), overrides)

    #
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('evm.vm.evm.EVM.{0}'.format(self.__class__.__name__))

    #
    # Execution
    #
    def apply_transaction(self, transaction):
        """
        Execution of a transaction in the EVM.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_create_message(self, message):
        """
        Execution of an EVM message to create a new contract.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_message(self, message):
        """
        Execution of an EVM message.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_computation(self, message):
        """
        Perform the computation that would be triggered by the EVM message.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Mining
    #
    def get_block_reward(self, block_number):
        return BLOCK_REWARD

    def get_nephew_reward(self, block_number):
        return NEPHEW_REWARD

    def mine_block(self, *args, **kwargs):
        """
        Mine the current block.
        """
        block = self.block.mine(*args, **kwargs)

        if block.number > 0:
            block_reward = self.get_block_reward(block.number) + (
                len(block.uncles) * self.get_nephew_reward(block.number)
            )

            self.state_db.delta_balance(block.header.coinbase, block_reward)

            for uncle in block.uncles:
                uncle_reward = block_reward * (
                    UNCLE_DEPTH_PENALTY_FACTOR + uncle.block_number - block.number
                ) // UNCLE_DEPTH_PENALTY_FACTOR
                self.state_db.delta_balance(uncle.coinbase, uncle_reward)

            block.header.state_root = self.state_db.root_hash

        return block

    #
    # Transactions
    #
    @classmethod
    def get_transaction_class(cls):
        """
        Return the class that this EVM uses for transactions.
        """
        return cls.get_block_class().get_transaction_class()

    def create_transaction(self, *args, **kwargs):
        """
        Proxy for instantiating a transaction for this EVM.
        """
        return self.get_transaction_class()(*args, **kwargs)

    def validate_transaction(self, transaction):
        """
        Perform evm-aware validation checks on the transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Blocks
    #
    _block_class = None

    @classmethod
    def get_block_class(cls):
        """
        Return the class that this EVM uses for blocks.
        """
        if cls._block_class is None:
            raise AttributeError("No `_block_class` has been set for this EVM")

        block_class = cls._block_class.configure(db=cls.db)
        return block_class

    def get_block_by_hash(self, block_hash):
        block_class = self.get_block_class()
        block = rlp.decode(self.db.get(block_hash), sedes=block_class, db=self.db)
        return block

    def get_block_hash(self, block_number):
        """
        For getting block hash for any block number in the the last 256 blocks.
        """
        raise NotImplementedError("Not yet implemented")

    #
    # Headers
    #
    def create_header_from_parent(self, parent_header, **header_params):
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

    #
    # Snapshot and Revert
    #
    def snapshot(self):
        """
        Perform a full snapshot of the current state of the EVM.

        TODO: This needs to do more than just snapshot the state_db but this is a start.
        """
        return self.state_db.snapshot()

    def revert(self, snapshot):
        """
        Revert the EVM to the state

        TODO: This needs to do more than just snapshot the state_db but this is a start.
        """
        return self.state_db.revert(snapshot)

    #
    # Opcode API
    #
    def get_opcode_fn(self, opcode):
        try:
            return self.opcodes[opcode]
        except KeyError:
            return InvalidOpcode(opcode)


class MetaEVM(object):
    """
    The MetaEVM combines multiple EVM classes into a single EVM.
    """
    db = None
    header = None

    evms_by_range = None

    def __init__(self, header):
        if self.db is None:
            raise ValueError("MetaEVM must be configured with a db")

        if not self.evms_by_range:
            raise ValueError("MetaEVM must be configured with block ranges")

        self.header = header

    @classmethod
    def configure(cls, name=None, evm_block_ranges=None, db=None):
        if evm_block_ranges is None:
            evms_by_range = cls.evms_by_range
        else:
            # Extract the block ranges for the provided EVMs
            if len(evm_block_ranges) == 1:
                # edge case for a single range.
                ranges = [evm_block_ranges[0][0]]
            else:
                raw_ranges, _ = zip(*evm_block_ranges)
                ranges = tuple(sorted(raw_ranges, key=range_sort_fn))

            # Validate that the block ranges define a continuous range of block
            # numbers with no gaps.
            validate_evm_block_ranges(ranges)

            # Organize the EVM classes by their respected ranges
            evms_by_range = {
                range: evm
                for range, evm
                in evm_block_ranges
            }

        if name is None:
            name = cls.__name__

        props = {
            'evms_by_range': evms_by_range,
            'db': db or cls.db,
        }
        return type(name, (cls,), props)

    #
    # EVM Operations
    #
    @classmethod
    def get_evm_class_for_block_number(cls, block_number):
        """
        Return the evm class for the given block number.
        """
        range = find_range(tuple(cls.evms_by_range.keys()), block_number)
        base_evm_class = cls.evms_by_range[range]
        evm_class = base_evm_class.configure(db=cls.db)
        return evm_class

    def get_evm(self, block_number=None):
        """
        Return the evm instance for the given block number.
        """
        if block_number is None:
            block_number = self.header.block_number

        evm_class = self.get_evm_class_for_block_number(block_number)
        evm = evm_class(header=self.header)
        return evm

    #
    # Block Retrieval
    #
    def get_block_by_number(self, block_number):
        """
        Returns the requested block as specified by block number.
        """
        # TODO: validate block number
        block_hash = self._lookup_block_hash(block_number)
        evm = self.get_evm(block_number)
        block = evm.get_block_by_hash(block_hash)
        return block

    def _lookup_block_hash(self, block_number):
        """
        Return the block hash for the given block number.
        """
        number_to_hash_key = make_block_number_to_hash_lookup_key(block_number)
        # TODO: can raise KeyError
        block_hash = rlp.decode(
            self.db.get(number_to_hash_key),
            sedes=rlp.sedes.binary,
        )
        return block_hash

    def get_block_by_hash(self, block_hash):
        """
        Returns the requested block as specified by block hash.

        TODO: how do we determine the correct EVM class?
        """
        # TODO: validate block hash
        block_number = self._lookup_block_number(block_hash)
        evm = self.get_evm(block_number)
        block = evm.get_block_by_hash(block_hash)
        return block

    def _lookup_block_number(self, block_hash):
        """
        Return the block number for the given block hash.
        """
        hash_to_number_key = make_block_hash_to_number_lookup_key(block_hash)
        # TODO: can raise KeyError
        block_number = rlp.decode(
            self.db.get(hash_to_number_key),
            sedes=rlp.sedes.big_endian_int,
        )
        return block_number

    #
    # EVM Initialization
    #
    @classmethod
    def from_genesis(cls,
                     genesis_params,
                     genesis_state=None):
        """
        Initialize the EVM from a genesis state.
        """
        if cls.db is None:
            raise ValueError("MetaEVM class must have a db")

        state_db = State(cls.db)

        if genesis_state is None:
            genesis_state = {}

        for account, account_data in genesis_state.items():
            state_db.set_balance(account, account_data['balance'])
            state_db.set_nonce(account, account_data['nonce'])
            state_db.set_code(account, account_data['code'])

            for slot, value in account_data['storage']:
                state_db.set_storage(account, slot, value)

        genesis_header = BlockHeader(**genesis_params)
        if genesis_header.state_root != state_db.root_hash:
            raise ValidationError(
                "The provided genesis state root does not match the computed "
                "genesis state root.  Got {0}.  Expected {1}".format(
                    state_db.root_hash,
                    genesis_header.state_root,
                )
            )

        meta_evm = cls(header=genesis_header)
        evm = meta_evm.get_evm()
        persist_block_to_db(meta_evm.db, evm.block)

        meta_evm.header = evm.create_header_from_parent(genesis_header)
        return meta_evm

    #
    # Mining and Execution API
    #
    def apply_transaction(self, txn_args=None, txn_kwargs=None):
        if txn_args is None:
            txn_args = tuple()
        if txn_kwargs is None:
            txn_kwargs = {}
        evm = self.get_evm()
        transaction = evm.create_transaction(*txn_args, **txn_kwargs)
        computation = evm.block.apply_transaction(evm, transaction)
        # icky mutation...
        self.header = evm.block.header
        return computation

    def mine_block(self, **mine_params):
        """
        Mine the current block, applying
        """
        evm = self.get_evm()

        block = evm.mine_block(**mine_params)
        persist_block_to_db(self.db, block)

        self.header = evm.create_header_from_parent(block.header)

        return block

    def configure_header(self, *args, **kwargs):
        evm = self.get_evm()
        self.header = evm.configure_header(*args, **kwargs)
        return self.header
