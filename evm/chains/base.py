from __future__ import absolute_import
import logging

from cytoolz import (
    assoc,
)

from eth_utils import (
    to_tuple,
)

from evm.consensus.pow import (
    check_pow,
)
from evm.constants import (
    MAX_UNCLE_DEPTH,
)
from evm.db.chain import AsyncChainDB
from evm.estimators import (
    get_gas_estimator,
)
from evm.exceptions import (
    BlockNotFound,
    TransactionNotFound,
    ValidationError,
    VMNotFound,
)
from evm.validation import (
    validate_block_number,
    validate_uint256,
    validate_word,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.utils.chain import (
    generate_vms_by_range,
)
from evm.utils.datatypes import (
    Configurable,
)
from evm.utils.headers import (
    compute_gas_limit_bounds,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.rlp import (
    ensure_imported_block_unchanged,
)


class BaseChain(Configurable):
    """
    The base class for all Chain objects
    """
    #
    # Chain Initialization API
    #
    @classmethod
    def from_genesis(cls,
                     chaindb,
                     genesis_params,
                     genesis_state=None):
        """
        Initializes the Chain from a genesis state.
        """
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    def from_genesis_header(cls, chaindb, genesis_header):
        """
        Initializes the chain from the genesis header.
        """
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Header API
    #
    def get_canonical_head(self):
        """
        Returns the block header at the canonical chain head.

        Raises CanonicalHeadNotFound if there's no head defined for the canonical chain.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def get_block_header_by_hash(self, block_hash):
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if there's no block header with the given hash in the db.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def create_header_from_parent(self, parent_header, **header_params):
        """
        Creates a new header descending from the given `parent_header`,
        initialized with the given `header_params`.
        """
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Block API
    #
    def get_block(self):
        """
        Returns the block at the tip of the chain.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def get_canonical_block_by_number(self, block_number):
        """
        Returns the block with the given number in the canonical chain.

        Raises BlockNotFound if there's no block with the given number in the
        canonical chain.
        """
        validate_uint256(block_number, title="Block Number")
        return self.get_block_by_hash(self.chaindb.lookup_block_hash(block_number))

    def get_block_by_hash(self, block_hash):
        """
        Returns the requested block as specified by block hash.
        """
        validate_word(block_hash, title="Block Hash")
        block_header = self.get_block_header_by_hash(block_hash)
        return self.get_block_by_header(block_header)

    def get_block_by_header(self, block_header):
        vm = self.get_vm(block_header)
        return vm.get_block_by_header(block_header, self.chaindb)

    @to_tuple
    def get_ancestors(self, limit):
        lower_limit = max(self.header.block_number - limit, 0)
        for n in reversed(range(lower_limit, self.header.block_number)):
            yield self.get_canonical_block_by_number(n)

    #
    # Transaction API
    #
    def get_canonical_transaction(self, transaction_hash):
        """
        Return the transaction for the given hash.  Raises
        `TransactionNotFound` if the transaction is not found on the canonical
        chain.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def add_pending_transaction(self, transaction):
        """
        Adds a transaction to the set of pending transactions.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def get_pending_transaction(self, transaction_hash):
        """
        Retrieves a transaction from the set of pending transactions.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def create_transaction(self, *args, **kwargs):
        """
        Creates a transaction object.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def create_unsigned_transaction(self, *args, **kwargs):
        """
        Creates an unsigned transaction object.
        """
        raise NotImplementedError("Chain classes must implement this method")

    #
    # VM API
    #
    def get_vm_class_for_block_number(self, block_number):
        """
        Returns the VM class for the given block number.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def get_vm(self, header=None):
        """
        Returns the VM instance for the given block number.
        """
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Execution API
    #
    def apply_transaction(self, transaction):
        """
        Applies the transaction to the current head block of the Chain.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def estimate_gas(self, transaction, at_header=None):
        """
        Generate a gas estimation for the given transaction using the
        configured gas estimator for this chain.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def import_block(self, block, perform_validation=True):
        """
        Imports a complete block.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def mine_block(self, *args, **kwargs):
        """
        Mines the current block. Proxies to the current Virtual Machine.
        See VM. :meth:`~evm.vm.base.VM.mine_block`
        """
        raise NotImplementedError("Chain classes must implement this method")

    def get_chain_at_block_parent(self, block):
        """
        Returns a `Chain` instance with the given block's parent at the chain head.
        """
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Validation API
    #
    def validate_block(self, block):
        """
        Performs validation on a block that is either being mined or imported.

        Since block validation (specifically the uncle validation must have
        access to the ancestor blocks, this validation must occur at the Chain
        level.

        TODO: move the `seal` validation down into the vm.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def validate_uncles(self, block):
        """
        Run validation on the block uncles.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def validate_seal(self, header):
        """
        Validate the seal on the given header.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def validate_gaslimit(self, header):
        """
        Validate the gas limit on the given header.
        """
        raise NotImplementedError("Chain classes must implement this method")


class Chain(BaseChain):
    """
    A Chain is a combination of one or more VM classes.  Each VM is associated
    with a range of blocks.  The Chain class acts as a wrapper around these other
    VM classes, delegating operations to the appropriate VM depending on the
    current block number.
    """
    logger = logging.getLogger("evm.chain.chain.Chain")
    header = None
    network_id = None
    vms_by_range = None
    gas_estimator = None

    def __init__(self, chaindb: AsyncChainDB, header=None):
        if not self.vms_by_range:
            raise ValueError(
                "The Chain class cannot be instantiated with an empty `vms_by_range`"
            )

        self.chaindb = chaindb  # type: AsyncChainDB
        self.header = header
        if self.header is None:
            self.header = self.create_header_from_parent(self.get_canonical_head())
        if self.gas_estimator is None:
            self.gas_estimator = get_gas_estimator()

    @classmethod
    def configure(cls, __name__=None, vm_configuration=None, **overrides):
        if 'vms_by_range' in overrides:
            raise ValueError("Cannot override vms_by_range")

        if vm_configuration is not None:
            overrides['vms_by_range'] = generate_vms_by_range(vm_configuration)
        return super().configure(__name__, **overrides)

    #
    # Convenience and Helpers
    #
    def get_block(self):
        """
        Passthrough helper to the current VM class.
        """
        return self.get_vm().block

    def get_canonical_transaction(self, transaction_hash):
        (block_num, index) = self.chaindb.get_transaction_index(transaction_hash)
        VM = self.get_vm_class_for_block_number(block_num)

        transaction = self.chaindb.get_transaction_by_index(
            block_num,
            index,
            VM.get_transaction_class(),
        )

        if transaction.hash == transaction_hash:
            return transaction
        else:
            raise TransactionNotFound("Found transaction {} instead of {} in block {} at {}".format(
                encode_hex(transaction.hash),
                encode_hex(transaction_hash),
                block_num,
                index,
            ))

    def add_pending_transaction(self, transaction):
        return self.chaindb.add_pending_transaction(transaction)

    def get_pending_transaction(self, transaction_hash):
        return self.get_vm().get_pending_transaction(transaction_hash)

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
        Returns the VM class for the given block number.
        """
        validate_block_number(block_number)
        for n in reversed(self.vms_by_range.keys()):
            if block_number >= n:
                return self.vms_by_range[n]
        else:
            raise VMNotFound("No vm available for block #{0}".format(block_number))

    def get_vm(self, header=None):
        """
        Returns the VM instance for the given block number.
        """
        if header is None:
            header = self.header

        vm_class = self.get_vm_class_for_block_number(header.block_number)
        return vm_class(header=header, chaindb=self.chaindb)

    #
    # Header/Block Retrieval
    #
    def get_block_header_by_hash(self, block_hash):
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if there's no block header with the given hash in the db.
        """
        validate_word(block_hash, title="Block Hash")
        return self.chaindb.get_block_header_by_hash(block_hash)

    def get_canonical_head(self):
        """
        Returns the block header at the canonical chain head.

        Raises CanonicalHeadNotFound if there's no head defined for the canonical chain.
        """
        return self.chaindb.get_canonical_head()

    def get_canonical_block_by_number(self, block_number):
        """
        Returns the block with the given number in the canonical chain.

        Raises BlockNotFound if there's no block with the given number in the
        canonical chain.
        """
        validate_uint256(block_number, title="Block Number")
        return self.get_block_by_hash(self.chaindb.lookup_block_hash(block_number))

    def get_block_by_hash(self, block_hash):
        """
        Returns the requested block as specified by block hash.
        """
        validate_word(block_hash, title="Block Hash")
        block_header = self.get_block_header_by_hash(block_hash)
        return self.get_block_by_header(block_header)

    def get_block_by_header(self, block_header):
        vm = self.get_vm(block_header)
        return vm.get_block_by_header(block_header, self.chaindb)

    #
    # Chain Initialization
    #
    @classmethod
    def from_genesis(cls,
                     chaindb,
                     genesis_params,
                     genesis_state=None):
        """
        Initializes the Chain from a genesis state.
        """
        state_db = chaindb.get_state_db(chaindb.empty_root_hash, read_only=False)

        if genesis_state is None:
            genesis_state = {}

        state_db.apply_state_dict(genesis_state)

        if 'state_root' not in genesis_params:
            # If the genesis state_root was not specified, use the value
            # computed from the initialized state database.
            genesis_params = assoc(genesis_params, 'state_root', state_db.root_hash)
        elif genesis_params['state_root'] != state_db.root_hash:
            # If the genesis state_root was specified, validate that it matches
            # the computed state from the initialized state database.
            raise ValidationError(
                "The provided genesis state root does not match the computed "
                "genesis state root.  Got {0}.  Expected {1}".format(
                    state_db.root_hash,
                    genesis_params['state_root'],
                )
            )

        genesis_header = BlockHeader(**genesis_params)
        genesis_chain = cls(chaindb, genesis_header)
        chaindb.persist_block(genesis_chain.get_block())
        return cls.from_genesis_header(chaindb, genesis_header)

    @classmethod
    def from_genesis_header(cls, chaindb, genesis_header):
        chaindb.persist_header(genesis_header)
        return cls(chaindb)

    #
    # Mining and Execution API
    #
    def apply_transaction(self, transaction):
        """
        Applies the transaction to the current head block of the Chain.
        """
        vm = self.get_vm()
        computation, block = vm.apply_transaction(transaction)

        # Update header
        self.header = block.header

        return computation

    def estimate_gas(self, transaction, at_header=None):
        if at_header is None:
            at_header = self.get_canonical_head()
        with self.get_vm(at_header).state_in_temp_block() as state:
            return self.gas_estimator(state, transaction)

    def import_block(self, block, perform_validation=True):
        """
        Imports a complete block.
        """
        if block.number > self.header.block_number:
            raise ValidationError(
                "Attempt to import block #{0}.  Cannot import block with number "
                "greater than current block #{1}.".format(
                    block.number,
                    self.header.block_number,
                )
            )

        parent_chain = self.get_chain_at_block_parent(block)
        imported_block = parent_chain.get_vm().import_block(block)

        # Validate the imported block.
        if perform_validation:
            ensure_imported_block_unchanged(imported_block, block)
            self.validate_block(imported_block)

        self.chaindb.persist_block(imported_block)
        self.header = self.create_header_from_parent(self.get_canonical_head())
        self.logger.debug(
            'IMPORTED_BLOCK: number %s | hash %s',
            imported_block.number,
            encode_hex(imported_block.hash),
        )
        return imported_block

    def mine_block(self, *args, **kwargs):
        """
        Mines the current block. Proxies to the current Virtual Machine.
        See VM. :meth:`~evm.vm.base.VM.mine_block`
        """
        mined_block = self.get_vm().mine_block(*args, **kwargs)

        self.validate_block(mined_block)

        self.chaindb.persist_block(mined_block)
        self.header = self.create_header_from_parent(self.get_canonical_head())
        return mined_block

    def get_chain_at_block_parent(self, block):
        """
        Returns a `Chain` instance with the given block's parent at the chain head.
        """
        try:
            parent_header = self.get_block_header_by_hash(block.header.parent_hash)
        except BlockNotFound:
            raise ValidationError("Parent ({0}) of block {1} not found".format(
                block.header.parent_hash,
                block.header.hash
            ))

        init_header = self.create_header_from_parent(parent_header)
        return type(self)(self.chaindb, init_header)

    @to_tuple
    def get_ancestors(self, limit):
        lower_limit = max(self.header.block_number - limit, 0)
        for n in reversed(range(lower_limit, self.header.block_number)):
            yield self.get_canonical_block_by_number(n)

    #
    # Validation API
    #
    def validate_block(self, block):
        """
        Performs validation on a block that is either being mined or imported.

        Since block validation (specifically the uncle validation must have
        access to the ancestor blocks, this validation must occur at the Chain
        level.

        TODO: move the `seal` validation down into the vm.
        """
        self.validate_seal(block.header)
        self.validate_uncles(block)
        self.validate_gaslimit(block.header)

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

    def validate_gaslimit(self, header):
        parent_header = self.get_block_header_by_hash(header.parent_hash)
        low_bound, high_bound = compute_gas_limit_bounds(parent_header)
        if header.gas_limit < low_bound:
            raise ValidationError(
                "The gas limit on block {0} is too low: {1}. It must be at least {2}".format(
                    encode_hex(header.hash), header.gas_limit, low_bound))
        elif header.gas_limit > high_bound:
            raise ValidationError(
                "The gas limit on block {0} is too high: {1}. It must be at most {2}".format(
                    encode_hex(header.hash), header.gas_limit, high_bound))
