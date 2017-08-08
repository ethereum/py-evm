from __future__ import absolute_import

import collections
from operator import itemgetter

from eth_utils import (
    pad_right,
    to_tuple,
)
from evm.consensus.pow import (
    check_pow,
)
from evm.constants import (
    GENESIS_BLOCK_NUMBER,
    MAX_UNCLE_DEPTH,
)
from evm.exceptions import (
    BlockNotFound,
    ValidationError,
    VMNotFound,
)
from evm.validation import (
    validate_block_number,
    validate_uint256,
    validate_vm_block_numbers,
    validate_word,
)

from evm.rlp.headers import (
    BlockHeader,
)

from evm.utils.blocks import (
    add_block_number_to_hash_lookup,
    get_score,
    get_block_header_by_hash,
    lookup_block_hash,
)
from evm.utils.blocks import (
    persist_block_to_db,
)
from evm.utils.hexidecimal import (
    encode_hex,
)
from evm.utils.rlp import diff_rlp_object

from evm.state import State


class Chain(object):
    """
    An Chain is a combination of one or more VM classes.  Each VM is associated
    with a range of blocks.  The Chain class acts as a wrapper around these other
    VM classes, delegating operations to the appropriate VM depending on the
    current block number.
    """
    db = None
    header = None

    vms_by_range = None

    def __init__(self, db, header):
        if not self.vms_by_range:
            raise ValueError(
                "The Chain class cannot be instantiated with an empty `vms_by_range`"
            )

        self.db = db
        self.header = header

    @classmethod
    def configure(cls, name, vm_configuration, **overrides):
        if 'vms_by_range' in overrides:
            raise ValueError("Cannot override vms_by_range.")

        for key in overrides:
            if not hasattr(cls, key):
                raise TypeError(
                    "The Chain.configure cannot set attributes that are not "
                    "already present on the base class.  The attribute `{0}` was "
                    "not found on the base class `{1}`".format(key, cls)
                )

        validate_vm_block_numbers(tuple(
            block_number
            for block_number, _
            in vm_configuration
        ))

        # Organize the Chain classes by their starting blocks.
        overrides['vms_by_range'] = collections.OrderedDict(
            sorted(vm_configuration, key=itemgetter(0)))

        return type(name, (cls,), overrides)

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
        Passthrough helper to the VM class of the block descending from the
        given header.
        """
        return self.get_vm_class_for_block_number(
            block_number=parent_header.block_number + 1,
        ).create_header_from_parent(parent_header, **header_params)

    #
    # Chain Operations
    #
    def get_vm_class_for_block_number(self, block_number):
        """
        Return the vm class for the given block number.
        """
        validate_block_number(block_number)
        for n in reversed(self.vms_by_range.keys()):
            if block_number >= n:
                return self.vms_by_range[n]
        else:
            raise VMNotFound("No vm available for block #{0}".format(block_number))

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
        return get_block_header_by_hash(self.db, block_hash)

    def get_canonical_block_by_number(self, block_number):
        """
        Returns the block with the given number in the canonical chain.

        Raises BlockNotFound if there's no block with the given number in the
        canonical chain.
        """
        validate_uint256(block_number)
        return self.get_block_by_hash(lookup_block_hash(self.db, block_number))

    def get_block_by_hash(self, block_hash):
        """
        Returns the requested block as specified by block hash.
        """
        validate_word(block_hash)
        block_header = self.get_block_header_by_hash(block_hash)
        vm = self.get_vm(block_header)
        return vm.get_block_by_header(block_header)

    #
    # Chain Initialization
    #
    @classmethod
    def from_genesis(cls,
                     db,
                     genesis_params,
                     genesis_state=None):
        """
        Initialize the Chain from a genesis state.
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

        genesis_chain = cls(db, genesis_header)
        persist_block_to_db(db, genesis_chain.get_block())
        add_block_number_to_hash_lookup(db, genesis_chain.get_block())

        return cls(db, genesis_chain.create_header_from_parent(genesis_header))

    #
    # Mining and Execution API
    #
    def apply_transaction(self, transaction):
        """
        Apply the transaction to the current head block of the Chain.
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

        parent_chain = self.get_parent_chain(block)
        imported_block = parent_chain.get_vm().import_block(block)
        self.ensure_blocks_are_equal(imported_block, block)
        # It feels wrong to call validate_block() on self here, but we do that
        # because we want to look up the recent uncles starting from the
        # current canonical chain head.
        self.validate_block(imported_block)

        persist_block_to_db(self.db, imported_block)
        if self.should_be_canonical_chain_head(imported_block):
            self.add_to_canonical_chain_head(imported_block)

        return imported_block

    def ensure_blocks_are_equal(self, block1, block2):
        if block1 == block2:
            return
        diff = diff_rlp_object(block1, block2)
        longest_field_name = max(len(field_name) for field_name, _, _ in diff)
        error_message = (
            "Mismatch between block and imported block on {0} fields:\n - {1}".format(
                len(diff),
                "\n - ".join(tuple(
                    "{0}:\n    (actual)  : {1}\n    (expected): {2}".format(
                        pad_right(field_name, longest_field_name, ' '),
                        actual,
                        expected,
                    )
                    for field_name, actual, expected
                    in diff
                )),
            )
        )
        raise ValidationError(error_message)

    def get_parent_chain(self, block):
        try:
            parent_header = self.get_block_header_by_hash(
                block.header.parent_hash)
        except BlockNotFound:
            raise ValidationError("Parent ({0}) of block {1} not found".format(
                block.header.parent_hash, block.header.hash))

        init_header = self.create_header_from_parent(parent_header)
        return type(self)(self.db, init_header)

    def should_be_canonical_chain_head(self, block):
        current_head = self.get_block_by_hash(self.header.parent_hash)
        return get_score(self.db, block.hash) > get_score(self.db, current_head.hash)

    def add_to_canonical_chain_head(self, block):
        for b in reversed(self.find_common_ancestor(block)):
            add_block_number_to_hash_lookup(self.db, b)
        self.header = self.create_header_from_parent(block.header)

    @to_tuple
    def find_common_ancestor(self, block):
        b = block
        while b.number >= GENESIS_BLOCK_NUMBER:
            yield b
            try:
                orig = self.get_canonical_block_by_number(b.number)
                if orig.hash == b.hash:
                    # Found the common ancestor, stop.
                    break
            except KeyError:
                # This just means the block is not on the canonical chain.
                pass
            b = self.get_block_by_hash(b.header.parent_hash)

    def validate_block(self, block):
        self.validate_seal(block.header)
        self.validate_uncles(block)

    def validate_uncles(self, block):
        recent_ancestors = dict(
            (ancestor.hash, ancestor)
            for ancestor in self.get_ancestors(MAX_UNCLE_DEPTH + 1),
        )
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
            blocks.append(self.get_canonical_block_by_number(n))
        return blocks
