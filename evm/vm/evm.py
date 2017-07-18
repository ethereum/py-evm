from __future__ import absolute_import

import collections
from operator import itemgetter

import rlp

from evm.consensus.pow import (
    check_pow,
)
from evm.constants import (
    MAX_UNCLE_DEPTH,
)
from evm.exceptions import (
    BlockNotFound,
    EVMNotFound,
    ValidationError,
)
from evm.validation import (
    validate_vm_block_numbers,
    validate_uint256,
    validate_word,
)

from evm.rlp.headers import (
    BlockHeader,
)

from evm.utils.blocks import (
    lookup_block_hash,
)
from evm.utils.blocks import (
    persist_block_to_db,
)
from evm.utils.hexidecimal import (
    encode_hex,
)

from evm.state import State


class EVM(object):
    """
    An EVM is a combination of one or more VM classes.  Each VM is associated
    with a range of blocks.  The EVM class acts as a wrapper around these other
    VM classes, delegating operations to the appropriate VM depending on the
    current block number.
    """
    db = None
    header = None

    vms_by_range = None

    def __init__(self, db, header):
        if self.vms_by_range is None:
            raise ValueError("MetaEVM must be configured with block ranges")

        self.db = db
        self.header = header

    @classmethod
    def configure(cls, name=None, vm_configuration=None):
        if vm_configuration is None:
            vms_by_range = cls.vms_by_range
        else:
            # Organize the EVM classes by their starting blocks.
            validate_vm_block_numbers(tuple(
                block_number
                for block_number, _
                in vm_configuration
            ))

            vms_by_range = collections.OrderedDict(sorted(vm_configuration, key=itemgetter(0)))

        if name is None:
            name = cls.__name__

        props = {
            'vms_by_range': vms_by_range,
        }
        return type(name, (cls,), props)

    #
    # Convenience and Helpers
    #
    def get_state_db(self):
        """
        Passthrough helper to the current VM class.
        """
        return self.get_vm().state_db

    def get_block(self):
        """
        Passthrough helper to the current VM class.
        """
        return self.get_vm().block

    def create_transaction(self, *args, **kwargs):
        """
        Passthrough helper to the current VM class.
        """
        return self.get_vm().create_transaction(*args, **kwargs)

    def create_unsigned_transaction(self, *args, **kwargs):
        """
        Passthrough helper to the current VM class.
        """
        return self.get_vm().create_unsigned_transaction(*args, **kwargs)

    def create_header_from_parent(self, parent_header, **header_params):
        """
        Passthrough helper to the current VM class.
        """
        return self.get_vm_class_for_block_number(
            block_number=parent_header.block_number + 1,
        ).create_header_from_parent(parent_header, **header_params)

    #
    # EVM Operations
    #
    def get_vm_class_for_block_number(self, block_number):
        """
        Return the vm class for the given block number.
        """
        for n in reversed(self.vms_by_range.keys()):
            if block_number >= n:
                return self.vms_by_range[n]
        raise EVMNotFound(
            "There is no EVM available for block #{0}".format(block_number))

    def get_vm(self, header=None):
        """
        Return the vm instance for the given block number.
        """
        if header is None:
            header = self.header

        vm_class = self.get_vm_class_for_block_number(header.block_number)
        return vm_class(header=header, db=self.db)

    #
    # Block Retrieval
    #
    def get_block_header_by_hash(self, block_hash):
        """
        Returns the requested block header as specified by block hash.

        Returns None if it is not present in the db.
        """
        validate_word(block_hash)
        try:
            block = self.db.get(block_hash)
        except KeyError:
            raise BlockNotFound("No block with hash {0} found".format(
                encode_hex(block_hash)))
        return rlp.decode(block, sedes=BlockHeader)

    def get_block_by_number(self, block_number):
        """
        Returns the requested block as specified by block number.

        Returns None if it is not present in the db.
        """
        validate_uint256(block_number)
        return self.get_block_by_hash(lookup_block_hash(self.db, block_number))

    def get_block_by_hash(self, block_hash):
        """
        Returns the requested block as specified by block hash.

        TODO: how do we determine the correct EVM class?
        """
        validate_word(block_hash)
        block_header = self.get_block_header_by_hash(block_hash)
        vm = self.get_vm(block_header)
        return vm.get_block_by_header(block_header)

    #
    # EVM Initialization
    #
    @classmethod
    def from_genesis(cls,
                     db,
                     genesis_params,
                     genesis_state=None):
        """
        Initialize the EVM from a genesis state.
        """
        state_db = State(db)

        if genesis_state is None:
            genesis_state = {}

        for account, account_data in genesis_state.items():
            state_db.set_balance(account, account_data['balance'])
            state_db.set_nonce(account, account_data['nonce'])
            state_db.set_code(account, account_data['code'])

            for slot, value in account_data['storage'].items():
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

        genesis_evm = cls(db, genesis_header)
        persist_block_to_db(db, genesis_evm.get_block())

        return cls(db, genesis_evm.create_header_from_parent(genesis_header))

    #
    # Mining and Execution API
    #
    def apply_transaction(self, transaction):
        """
        Apply the transaction to the current head block of the EVM.
        """
        vm = self.get_vm()
        return vm.apply_transaction(transaction)

    def import_block(self, block):
        """
        Import a complete block.
        """
        if block.number > self.header.block_number:
            raise ValidationError(
                "Attempt to import block #{0}.  Cannot import block with number "
                "greater than current block #{1}.".format(
                    block.number,
                    self.header.block_number,
                )
            )

        try:
            parent_header = self.get_block_header_by_hash(
                block.header.parent_hash)
        except BlockNotFound:
            raise ValidationError("Parent ({0}) of block {1} not found".format(
                block.header.parent_hash, block.header.hash))
        init_header = self.create_header_from_parent(parent_header)
        parent_evm = type(self)(self.db, init_header)
        imported_block = parent_evm.get_vm().import_block(block)
        self.validate_block(imported_block)

        persist_block_to_db(self.db, imported_block)
        # TODO: We must only do this when the imported block has higher
        # score than current head.
        self.header = self.create_header_from_parent(imported_block.header)

        return imported_block

    def mine_block(self, **mine_params):
        """
        Mine the current block, applying
        """
        block = self.get_vm().mine_block(**mine_params)
        self.validate_block(block)
        persist_block_to_db(self.db, block)

        self.header = self.create_header_from_parent(block.header)

        return block

    def validate_block(self, block):
        self.validate_seal(block.header)
        self.validate_uncles(block)

    def validate_uncles(self, block):
        recent_ancestors = dict(
            (ancestor.hash, ancestor)
            for ancestor in self.get_ancestors(MAX_UNCLE_DEPTH+1))
        recent_uncles = []
        for ancestor in recent_ancestors.values():
            recent_uncles.extend([uncle.hash for uncle in ancestor.uncles])
        recent_ancestors[block.hash] = block
        recent_uncles.append(block.hash)

        for uncle in block.uncles:
            if uncle.hash in recent_ancestors:
                raise ValidationError(
                    "Duplicate uncle: {0}".format(encode_hex(uncle.hash)))
            recent_uncles.append(uncle.hash)

            if uncle.hash in recent_ancestors:
                raise ValidationError(
                    "Uncle {0} cannot be an ancestor of {1}".format(
                        encode_hex(uncle.hash), encode_hex(block.hash)))

            if uncle.parent_hash not in recent_ancestors or (
               uncle.parent_hash == block.header.parent_hash):
                raise ValidationError(
                    "Uncle's parent {0} is not an ancestor of {1}".format(
                        encode_hex(uncle.parent_hash), encode_hex(block.hash)))

            self.validate_seal(uncle)

    def validate_seal(self, header):
        check_pow(
            header.block_number, header.mining_hash,
            header.mix_hash, header.nonce, header.difficulty)

    def get_ancestors(self, limit):
        blocks = []
        lower_limit = max(self.header.block_number - limit, 0)
        for n in reversed(range(lower_limit, self.header.block_number)):
            blocks.append(self.get_block_by_number(n))
        return blocks
