from contextlib import contextmanager
import logging

from evm.vm.computation import (
    Computation,
)
from evm.exceptions import (
    Halt,
)
from evm.logic.invalid import (
    InvalidOpcode,
)


class BaseState(object):
    chaindb = None
    block = None
    opcodes = None
    precompiles = None

    def __init__(self, chaindb, block, opcodes, precompiles):
        self.chaindb = chaindb
        self.block = block
        self.opcodes = opcodes
        self.precompiles = precompiles

    def apply_message(self, message):
        """
        Execution of an VM message.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_create_message(self, message):
        """
        Execution of an VM message to create a new contract.
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
                opcode_fn = self.get_opcode_fn(self.opcodes, opcode)

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
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('evm.vm.state.{0}'.format(self.__class__.__name__))

    #
    # Opcode API
    #
    def get_opcode_fn(self, opcodes, opcode):
        try:
            return opcodes[opcode]
        except KeyError:
            return InvalidOpcode(opcode)

    #
    # Block Object Properties (in opcodes)
    #
    @property
    def blockhash(self):
        return self.block.hash

    @property
    def coinbase(self):
        return self.block.header.coinbase

    @property
    def timestamp(self):
        return self.block.header.timestamp

    @property
    def number(self):
        return self.block.header.block_number

    @property
    def difficulty(self):
        return self.block.header.difficulty

    @property
    def gaslimit(self):
        return self.block.header.gas_limit

    #
    # state_db
    #
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

    def get_ancestor_hash(self, block_number):
        """
        Return the hash for the ancestor with the given number
        """
        ancestor_depth = self.block.number - block_number
        if ancestor_depth > 256 or ancestor_depth < 1:
            return b''
        header = self.chaindb.get_block_header_by_hash(self.block.header.parent_hash)
        while header.block_number != block_number:
            header = self.chaindb.get_block_header_by_hash(header.parent_hash)
        return header.hash

    #
    # classmethod
    #
    @classmethod
    def create_state(cls, chaindb, block, opcodes, precompiles):
        return cls(chaindb, block, opcodes, precompiles)

    @classmethod
    def configure(cls,
                  name,
                  **overrides):
        """
        Class factory method for simple inline subclassing.
        """
        for key in overrides:
            if not hasattr(cls, key):
                raise TypeError(
                    "The State.configure cannot set attributes that are not "
                    "already present on the base class.  The attribute `{0}` was "
                    "not found on the base class `{1}`".format(key, cls)
                )
        return type(name, (cls,), overrides)
