from __future__ import absolute_import

import logging

from evm.constants import (
    BLOCK_REWARD,
    NEPHEW_REWARD,
    UNCLE_DEPTH_PENALTY_FACTOR,
)
from evm.logic.invalid import (
    InvalidOpcode,
)


from evm.state import State


class VM(object):
    """
    The VM class represents the EVM for a specific protocol definition.
    Defining an EVM for an ethereum network involves defining individual VM
    classes for each protocol fork within that network.
    """
    db = None

    block = None

    opcodes = None
    block_class = None

    def __init__(self, evm, db):
        if db is None:
            raise ValueError("VM classes must have a `db`")

        self.db = db
        self.evm = evm

        block_class = self.get_block_class()
        self.block = block_class.from_header(header=self.evm.header, db=db)
        self.state_db = State(db=self.db, root_hash=self.evm.header.state_root)

    @classmethod
    def configure(cls,
                  name=None,
                  **overrides):
        if name is None:
            name = cls.__name__

        for key in overrides:
            if not hasattr(cls, key):
                raise TypeError(
                    "The VM.configure cannot set attributes that are not "
                    "already present on the base class.  The attribute `{0}` was "
                    "not found on the base class `{1}`".format(key, cls)
                )
        return type(name, (cls,), overrides)

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
        Execution of a transaction within the VM.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_create_message(self, message):
        """
        Execution of an VM message to create a new contract.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_message(self, message):
        """
        Execution of an VM message.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_computation(self, message):
        """
        Perform the computation that would be triggered by the VM message.
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
    def get_transaction_class(self):
        """
        Return the class that this VM uses for transactions.
        """
        return self.get_block_class().get_transaction_class()

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

    def validate_transaction(self, transaction):
        """
        Perform evm-aware validation checks on the transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Blocks
    #
    _block_class = None

    def get_block_class(self):
        """
        Return the class that this VM uses for blocks.
        """
        if self._block_class is None:
            raise AttributeError("No `_block_class` has been set for this VM")

        return self._block_class

    def get_block_by_hash(self, block_hash):
        block_header = self.evm.get_block_header_by_hash(block_hash)
        block_class = self.get_block_class()
        block = block_class.from_header(block_header, self.db)
        return block

    def get_block_hash(self, block_number):
        """
        For getting block hash for any block number in the the last 256 blocks.
        """
        ancestor_depth = self.block.number - block_number
        if 1 <= ancestor_depth <= 256:
            return self.evm.get_block_by_number(block_number).header.hash
        else:
            return b''

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
        Perform a full snapshot of the current state of the VM.

        TODO: This needs to do more than just snapshot the state_db but this is a start.
        """
        return self.state_db.snapshot()

    def revert(self, snapshot):
        """
        Revert the VM to the state

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
