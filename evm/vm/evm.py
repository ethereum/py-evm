from __future__ import absolute_import

import collections
from operator import itemgetter

import rlp

from evm.exceptions import (
    EVMNotFound,
    ValidationError,
)
from evm.validation import (
    validate_vm_block_numbers,
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

    def __init__(self, header):
        if self.db is None:
            raise ValueError("MetaEVM must be configured with a db")

        if not self.vms_by_range:
            raise ValueError("MetaEVM must be configured with block ranges")

        self.header = header

    @classmethod
    def configure(cls, name=None, vm_configuration=None, db=None):
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
            'db': db or cls.db,
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

    def create_header_from_parent(self, *args, **kwargs):
        """
        Passthrough helper to the current VM class.
        """
        return self.get_vm().create_header_from_parent(*args, **kwargs)

    #
    # EVM Operations
    #
    @classmethod
    def get_vm_class_for_block_number(cls, block_number):
        """
        Return the vm class for the given block number.
        """
        for n in reversed(cls.vms_by_range.keys()):
            if block_number >= n:
                return cls.vms_by_range[n]
        raise EVMNotFound(
            "There is no EVM available for block #{0}".format(block_number))

    def get_vm(self, block_number=None):
        """
        Return the vm instance for the given block number.
        """
        if block_number is None:
            block_number = self.header.block_number

        vm_class = self.get_vm_class_for_block_number(block_number).configure(db=self.db)
        return vm_class(evm=self)

    #
    # Block Retrieval
    #
    def get_block_header_by_hash(self, block_hash):
        block_header = rlp.decode(self.db.get(block_hash), sedes=BlockHeader)
        return block_header

    def get_block_by_number(self, block_number):
        """
        Returns the requested block as specified by block number.
        """
        # TODO: validate block number
        block_hash = self._lookup_block_hash(block_number)
        vm = self.get_vm(block_number)
        block = vm.get_block_by_hash(block_hash)
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
        vm = self.get_vm(block_number)
        block = vm.get_block_by_hash(block_hash)
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

        evm = cls(header=genesis_header)
        persist_block_to_db(evm.db, evm.get_block())

        evm.header = evm.create_header_from_parent(genesis_header)
        return evm

    #
    # Mining and Execution API
    #
    def apply_transaction(self, transaction):
        """
        Apply the transaction to the current head block of the EVM.
        """
        vm = self.get_vm()
        computation = vm.apply_transaction(transaction)
        block = vm.block.add_transaction(
            transaction=transaction,
            computation=computation,
        )
        # TODO: icky mutation...
        self.header = block.header
        return computation

    def mine_block(self, **mine_params):
        """
        Mine the current block, applying
        """
        vm = self.get_vm()

        block = vm.mine_block(**mine_params)
        persist_block_to_db(self.db, block)

        self.header = vm.create_header_from_parent(block.header)

        return block

    def configure_header(self, *args, **kwargs):
        vm = self.get_vm()
        self.header = vm.configure_header(*args, **kwargs)
        return self.header
