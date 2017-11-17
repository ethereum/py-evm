from __future__ import absolute_import

import rlp

from contextlib import contextmanager
import logging

from evm.constants import (
    BLOCK_REWARD,
    UNCLE_DEPTH_PENALTY_FACTOR,
)
from evm.exceptions import (
    Halt,
)
from evm.logic.invalid import (
    InvalidOpcode,
)
from evm.utils.keccak import (
    keccak,
)

from .computation import (
    Computation,
)


class VM(object):
    """
    The VM class represents the Chain rules for a specific protocol definition
    such as the Frontier or Homestead network.  Defining an Chain  defining
    individual VM classes for each fork of the protocol rules within that
    network.
    """
    chaindb = None
    opcodes = None
    _block_class = None
    _precompiles = None

    def __init__(self, header, chaindb):
        self.chaindb = chaindb
        block_class = self.get_block_class()
        self.block = block_class.from_header(header=header, chaindb=self.chaindb)

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

    @contextmanager
    def state_db(self, read_only=False):
        state = self.chaindb.get_state_db(self.block.header.state_root, read_only)
        yield state

        if read_only:
            # This acts as a secondary check that no mutation took place for
            # read_only databases.
            assert state.root_hash == self.block.header.state_root
        elif self.block.header.state_root != state.root_hash:
            self.block.header.state_root = state.root_hash

        # remove the reference to the underlying `db` object to ensure that no
        # further modifications can occur using the `State` object after
        # leaving the context.
        state.db = None
        state._trie = None

    @property
    def precompiles(self):
        if self._precompiles is None:
            return set()
        else:
            return self._precompiles

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
        self.clear_journal()
        self.block.add_transaction(transaction, computation)
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
        with Computation(self, message) as computation:
            # Early exit on pre-compiles
            if message.code_address in self.precompiles:
                self.precompiles[message.code_address](computation)
                return computation

            for opcode in computation.code:
                opcode_fn = self.get_opcode_fn(opcode)

                computation.logger.trace(
                    "OPCODE: 0x%x (%s) | pc: %s",
                    opcode,
                    opcode_fn.mnemonic,
                    max(0, computation.code.pc - 1),
                )

                try:
                    opcode_fn(computation=computation)
                except Halt:
                    break
        return computation

    #
    # Mining
    #
    def get_block_reward(self, block_number):
        return BLOCK_REWARD

    def get_nephew_reward(self, block_number):
        return self.get_block_reward(block_number) // 32

    def get_uncle_reward(self, block_number, uncle):
        return BLOCK_REWARD * (
            UNCLE_DEPTH_PENALTY_FACTOR + uncle.block_number - block_number
        ) // UNCLE_DEPTH_PENALTY_FACTOR

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
        Mine the current block.
        """
        block = self.block
        block.mine(*args, **kwargs)

        if block.number == 0:
            return block

        block_reward = self.get_block_reward(block.number) + (
            len(block.uncles) * self.get_nephew_reward(block.number)
        )

        with self.state_db() as state_db:
            state_db.delta_balance(block.header.coinbase, block_reward)
            self.logger.debug(
                "BLOCK REWARD: %s -> %s",
                block_reward,
                block.header.coinbase,
            )

            for uncle in block.uncles:
                uncle_reward = self.get_uncle_reward(block.number, uncle)
                state_db.delta_balance(uncle.coinbase, uncle_reward)
                self.logger.debug(
                    "UNCLE REWARD REWARD: %s -> %s",
                    uncle_reward,
                    uncle.coinbase,
                )

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
        return self.get_block_class().from_header(block_header, self.chaindb)

    def get_ancestor_hash(self, block_number):
        """
        Return the hash for the ancestor with the given number
        """
        ancestor_depth = self.block.number - block_number
        if ancestor_depth > 256 or ancestor_depth < 1:
            return b''
        h = self.chaindb.get_block_header_by_hash(self.block.header.parent_hash)
        while h.block_number != block_number:
            h = self.chaindb.get_block_header_by_hash(h.parent_hash)
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

        Snapshots are a combination of the state_root at the time of the
        snapshot and the checkpoint_id returned from the journaled DB.
        """
        return (self.block.header.state_root, self.chaindb.snapshot())

    def revert(self, snapshot):
        """
        Revert the VM to the state at the snapshot
        """
        state_root, checkpoint_id = snapshot

        with self.state_db() as state_db:
            # first revert the database state root.
            state_db.root_hash = state_root
            # now roll the underlying database back
            self.chaindb.revert(checkpoint_id)

    def commit(self, snapshot):
        """
        Commits the journal to the point where the snapshot was taken.  This
        will destroy any journal checkpoints *after* the snapshot checkpoint.
        """
        _, checkpoint_id = snapshot
        self.chaindb.commit(checkpoint_id)

    def clear_journal(self):
        """
        Cleare the journal.  This should be called at any point of VM execution
        where the statedb is being committed, such as after a transaction has
        been applied to a block.
        """
        self.chaindb.clear()

    #
    # Opcode API
    #
    def get_opcode_fn(self, opcode):
        try:
            return self.opcodes[opcode]
        except KeyError:
            return InvalidOpcode(opcode)
