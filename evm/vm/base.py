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
from evm.state import (
    State,
)

from evm.utils.blocks import (
    get_block_header_by_hash,
)


class VM(object):
    """
    The VM class represents the Chain rules for a specific protocol definition
    such as the Frontier or Homestead network.  Defining an Chain  defining
    individual VM classes for each fork of the protocol rules within that
    network.
    """
    db = None

    opcodes = None
    _block_class = None

    def __init__(self, header, db):
        if db is None:
            raise ValueError("VM classes must have a `db`")

        self.db = db

        block_class = self.get_block_class()
        self.block = block_class.from_header(header=header, db=db)

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

    _block = None
    state_db = None

    @property
    def block(self):
        if self._block is None:
            raise AttributeError("No block property set")
        return self._block

    @block.setter
    def block(self, value):
        self._block = value
        self.state_db = State(db=self.db, root_hash=value.header.state_root)

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
        computation = self.execute_transaction(transaction)
        # NOTE: mutation. Needed in order to update self.state_db, so we should be able to get rid
        # of this once we fix https://github.com/pipermerriam/py-evm/issues/67
        self.block = self.block.add_transaction(
            transaction=transaction,
            computation=computation,
        )
        return computation

    def execute_transaction(self, transaction):
        """
        Execute the transaction in the vm.
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

    def import_block(self, block):
        self.configure_header(
            coinbase=block.header.coinbase,
            gas_limit=block.header.gas_limit,
            timestamp=block.header.timestamp,
            extra_data=block.header.extra_data,
            mix_hash=block.header.mix_hash,
            nonce=block.header.nonce,
        )

        for transaction in block.transactions:
            self.apply_transaction(transaction)

        for uncle in block.uncles:
            self.block.add_uncle(uncle)

        return self.mine_block()

    def mine_block(self, *args, **kwargs):
        """
        Mine the current block.
        """
        block = self.block
        block.mine(*args, **kwargs)

        if block.number > 0:
            block_reward = self.get_block_reward(block.number) + (
                len(block.uncles) * self.get_nephew_reward(block.number)
            )

            self.state_db.delta_balance(block.header.coinbase, block_reward)
            self.logger.debug(
                "BLOCK REWARD: %s -> %s",
                block_reward,
                block.header.coinbase,
            )

            for uncle in block.uncles:
                uncle_reward = BLOCK_REWARD * (
                    UNCLE_DEPTH_PENALTY_FACTOR + uncle.block_number - block.number
                ) // UNCLE_DEPTH_PENALTY_FACTOR
                self.state_db.delta_balance(uncle.coinbase, uncle_reward)
                self.logger.debug(
                    "UNCLE REWARD REWARD: %s -> %s",
                    uncle_reward,
                    uncle.coinbase,
                )

            self.logger.debug('BEFORE ROOT: %s', block.header.state_root)
            block.header.state_root = self.state_db.root_hash
            self.logger.debug('STATE_ROOT: %s', block.header.state_root)

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
        Perform chain-aware validation checks on the transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")

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

    def get_block_by_header(self, block_header):
        return self.get_block_class().from_header(block_header, self.db)

    def get_ancestor_hash(self, block_number):
        """
        Return the hash for the ancestor with the given number
        """
        ancestor_depth = self.block.number - block_number
        if ancestor_depth > 256 or ancestor_depth < 1:
            return b''
        h = get_block_header_by_hash(self.db, self.block.header.parent_hash)
        while h.block_number != block_number:
            h = get_block_header_by_hash(self.db, h.parent_hash)
        return h.hash

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
