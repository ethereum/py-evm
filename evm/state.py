from contextlib import contextmanager

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

    def __init__(self, chaindb, block):
        self.chaindb = chaindb
        self.block = block

    def apply_computation(self, message, opcodes, precompiles):
        """
        Perform the computation that would be triggered by the VM message.
        """
        with Computation(self, message) as computation:
            # Early exit on pre-compiles
            if message.code_address in precompiles:
                precompiles[message.code_address](computation)
                return computation

            for opcode in computation.code:
                opcode_fn = self.get_opcode_fn(opcodes, opcode)

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
    # classmethod
    #
    @classmethod
    def create_state(cls, chaindb, block):
        return BaseState(chaindb, block)
