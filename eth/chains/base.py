from __future__ import absolute_import

from abc import (
    ABC,
    abstractmethod
)
import operator
import random
from typing import (  # noqa: F401
    Any,
    Callable,
    cast,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)

import logging

from cytoolz import (
    assoc,
    compose,
    groupby,
    iterate,
    take,
)

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
)

from eth_utils import (
    to_set,
    ValidationError,
)

from eth.db.backends.base import BaseAtomicDB
from eth.db.chain import (
    BaseChainDB,
    ChainDB,
)
from eth.db.header import (
    HeaderDB,
)
from eth.constants import (
    BLANK_ROOT_HASH,
    EMPTY_UNCLE_HASH,
    MAX_UNCLE_DEPTH,
)
from eth.estimators import (
    get_gas_estimator,
)
from eth.exceptions import (
    HeaderNotFound,
    TransactionNotFound,
    VMNotFound,
)
from eth.utils.spoof import (
    SpoofTransaction,
)
from eth.validation import (
    validate_block_number,
    validate_uint256,
    validate_word,
    validate_vm_configuration,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.rlp.headers import (
    BlockHeader,
    HeaderParams,
)
from eth.rlp.receipts import (
    Receipt,
)
from eth.rlp.transactions import (
    BaseTransaction,
    BaseUnsignedTransaction,
)
from eth.utils.db import (
    apply_state_dict,
)
from eth.utils.datatypes import (
    Configurable,
)
from eth.utils.headers import (
    compute_gas_limit_bounds,
)
from eth.utils.hexadecimal import (
    encode_hex,
)
from eth.utils.rlp import (
    validate_imported_block_unchanged,
)

if TYPE_CHECKING:
    from eth.vm.base import BaseVM  # noqa: F401


# Mapping from address to account state.
# 'balance', 'nonce' -> int
# 'code' -> bytes
# 'storage' -> Dict[int, int]
AccountState = Dict[Address, Dict[str, Union[int, bytes, Dict[int, int]]]]


class BaseChain(Configurable, ABC):
    """
    The base class for all Chain objects
    """
    chaindb = None  # type: BaseChainDB
    chaindb_class = None  # type: Type[BaseChainDB]
    vm_configuration = None  # type: Tuple[Tuple[int, Type[BaseVM]], ...]
    network_id = None  # type: int

    @abstractmethod
    def __init__(self) -> None:
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Helpers
    #
    @classmethod
    @abstractmethod
    def get_chaindb_class(cls) -> Type[BaseChainDB]:
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    def get_vm_configuration(cls) -> Tuple[Tuple[int, Type['BaseVM']], ...]:
        return cls.vm_configuration

    #
    # Chain API
    #
    @classmethod
    @abstractmethod
    def from_genesis(cls,
                     base_db: BaseAtomicDB,
                     genesis_params: Dict[str, HeaderParams],
                     genesis_state: AccountState=None) -> 'BaseChain':
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    @abstractmethod
    def from_genesis_header(cls,
                            base_db: BaseAtomicDB,
                            genesis_header: BlockHeader) -> 'BaseChain':
        raise NotImplementedError("Chain classes must implement this method")

    #
    # VM API
    #
    @classmethod
    def get_vm_class(cls, header: BlockHeader) -> Type['BaseVM']:
        """
        Returns the VM instance for the given block number.
        """
        return cls.get_vm_class_for_block_number(header.block_number)

    @abstractmethod
    def get_vm(self, header: BlockHeader=None) -> 'BaseVM':
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    def get_vm_class_for_block_number(cls, block_number: BlockNumber) -> Type['BaseVM']:
        """
        Returns the VM class for the given block number.
        """
        if cls.vm_configuration is None:
            raise AttributeError("Chain classes must define the VMs in vm_configuration")

        validate_block_number(block_number)
        for start_block, vm_class in reversed(cls.vm_configuration):
            if block_number >= start_block:
                return vm_class
        else:
            raise VMNotFound("No vm available for block #{0}".format(block_number))

    #
    # Header API
    #
    @abstractmethod
    def create_header_from_parent(self,
                                  parent_header: BlockHeader,
                                  **header_params: HeaderParams) -> BlockHeader:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_canonical_head(self):
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_score(self, block_hash):
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Block API
    #
    @abstractmethod
    def get_ancestors(self, limit: int, header: BlockHeader) -> Tuple[BaseBlock, ...]:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_block(self) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_block_by_hash(self, block_hash: Hash32) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_block_by_header(self, block_header: BlockHeader) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_canonical_block_by_number(self, block_number: BlockNumber) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_canonical_block_hash(self, block_number):
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def build_block_with_transactions(self, transactions, parent_header):
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Transaction API
    #
    @abstractmethod
    def create_transaction(self, *args: Any, **kwargs: Any) -> BaseTransaction:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def create_unsigned_transaction(self,
                                    *args: Any,
                                    **kwargs: Any) -> BaseUnsignedTransaction:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_canonical_transaction(self, transaction_hash: Hash32) -> BaseTransaction:
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Execution API
    #
    @abstractmethod
    def get_transaction_result(
            self,
            transaction: Union[BaseTransaction, SpoofTransaction],
            at_header: BlockHeader) -> bytes:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def estimate_gas(
            self,
            transaction: Union[BaseTransaction, SpoofTransaction],
            at_header: BlockHeader=None) -> int:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def import_block(self,
                     block: BaseBlock,
                     perform_validation: bool=True,
                     ) -> Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]]:
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Validation API
    #
    @abstractmethod
    def validate_receipt(self, receipt: Receipt, at_header: BlockHeader) -> None:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def validate_block(self, block: BaseBlock) -> None:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def validate_seal(self, header: BlockHeader) -> None:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def validate_gaslimit(self, header: BlockHeader) -> None:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def validate_uncles(self, block: BaseBlock) -> None:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def validate_chain(
            self,
            parent: BlockHeader,
            chain: Tuple[BlockHeader, ...],
            seal_check_random_sample_rate: int = 1) -> None:
        raise NotImplementedError("Chain classes must implement this method")


class Chain(BaseChain):
    """
    A Chain is a combination of one or more VM classes.  Each VM is associated
    with a range of blocks.  The Chain class acts as a wrapper around these other
    VM classes, delegating operations to the appropriate VM depending on the
    current block number.
    """
    logger = logging.getLogger("eth.chain.chain.Chain")
    gas_estimator = None  # type: Callable

    chaindb_class = ChainDB  # type: Type[BaseChainDB]

    def __init__(self, base_db: BaseAtomicDB) -> None:
        if not self.vm_configuration:
            raise ValueError(
                "The Chain class cannot be instantiated with an empty `vm_configuration`"
            )
        else:
            validate_vm_configuration(self.vm_configuration)

        self.chaindb = self.get_chaindb_class()(base_db)
        self.headerdb = HeaderDB(base_db)
        if self.gas_estimator is None:
            self.gas_estimator = get_gas_estimator()  # type: ignore

    #
    # Helpers
    #
    @classmethod
    def get_chaindb_class(cls) -> Type[BaseChainDB]:
        if cls.chaindb_class is None:
            raise AttributeError("`chaindb_class` not set")
        return cls.chaindb_class

    #
    # Chain API
    #
    @classmethod
    def from_genesis(cls,
                     base_db: BaseAtomicDB,
                     genesis_params: Dict[str, HeaderParams],
                     genesis_state: AccountState=None) -> 'BaseChain':
        """
        Initializes the Chain from a genesis state.
        """
        genesis_vm_class = cls.get_vm_class_for_block_number(BlockNumber(0))

        account_db = genesis_vm_class.get_state_class().get_account_db_class()(
            base_db,
            BLANK_ROOT_HASH,
        )

        if genesis_state is None:
            genesis_state = {}

        # mutation
        apply_state_dict(account_db, genesis_state)
        account_db.persist()

        if 'state_root' not in genesis_params:
            # If the genesis state_root was not specified, use the value
            # computed from the initialized state database.
            genesis_params = assoc(genesis_params, 'state_root', account_db.state_root)
        elif genesis_params['state_root'] != account_db.state_root:
            # If the genesis state_root was specified, validate that it matches
            # the computed state from the initialized state database.
            raise ValidationError(
                "The provided genesis state root does not match the computed "
                "genesis state root.  Got {0}.  Expected {1}".format(
                    account_db.state_root,
                    genesis_params['state_root'],
                )
            )

        genesis_header = BlockHeader(**genesis_params)
        return cls.from_genesis_header(base_db, genesis_header)

    @classmethod
    def from_genesis_header(cls,
                            base_db: BaseAtomicDB,
                            genesis_header: BlockHeader) -> 'BaseChain':
        """
        Initializes the chain from the genesis header.
        """
        chaindb = cls.get_chaindb_class()(base_db)
        chaindb.persist_header(genesis_header)
        return cls(base_db)

    #
    # VM API
    #
    def get_vm(self, at_header: BlockHeader=None) -> 'BaseVM':
        """
        Returns the VM instance for the given block number.
        """
        header = self.ensure_header(at_header)
        vm_class = self.get_vm_class_for_block_number(header.block_number)
        return vm_class(header=header, chaindb=self.chaindb)

    #
    # Header API
    #
    def create_header_from_parent(self, parent_header, **header_params):
        """
        Passthrough helper to the VM class of the block descending from the
        given header.
        """
        return self.get_vm_class_for_block_number(
            block_number=parent_header.block_number + 1,
        ).create_header_from_parent(parent_header, **header_params)

    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
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

    def get_score(self, block_hash):
        """
        Returns the difficulty score of the block with the given hash.

        Raises HeaderNotFound if there is no matching black hash.
        """
        return self.headerdb.get_score(block_hash)

    def ensure_header(self, header: BlockHeader=None) -> BlockHeader:
        """
        Return ``header`` if it is not ``None``, otherwise return the header
        of the canonical head.
        """
        if header is None:
            head = self.get_canonical_head()
            return self.create_header_from_parent(head)
        else:
            return header

    #
    # Block API
    #
    def get_ancestors(self, limit: int, header: BlockHeader) -> Tuple[BaseBlock, ...]:
        """
        Return `limit` number of ancestor blocks from the current canonical head.
        """
        ancestor_count = min(header.block_number, limit)

        # We construct a temporary block object
        vm_class = self.get_vm_class_for_block_number(header.block_number)
        block_class = vm_class.get_block_class()
        block = block_class(header=header, uncles=[])

        ancestor_generator = iterate(compose(
            self.get_block_by_hash,
            operator.attrgetter('parent_hash'),
            operator.attrgetter('header'),
        ), block)
        # we peel off the first element from the iterator which will be the
        # temporary block object we constructed.
        next(ancestor_generator)

        return tuple(take(ancestor_count, ancestor_generator))

    def get_block(self) -> BaseBlock:
        """
        Returns the current TIP block.
        """
        return self.get_vm().block

    def get_block_by_hash(self, block_hash: Hash32) -> BaseBlock:
        """
        Returns the requested block as specified by block hash.
        """
        validate_word(block_hash, title="Block Hash")
        block_header = self.get_block_header_by_hash(block_hash)
        return self.get_block_by_header(block_header)

    def get_block_by_header(self, block_header):
        """
        Returns the requested block as specified by the block header.
        """
        vm = self.get_vm(block_header)
        return vm.block

    def get_canonical_block_by_number(self, block_number: BlockNumber) -> BaseBlock:
        """
        Returns the block with the given number in the canonical chain.

        Raises BlockNotFound if there's no block with the given number in the
        canonical chain.
        """
        validate_uint256(block_number, title="Block Number")
        return self.get_block_by_hash(self.chaindb.get_canonical_block_hash(block_number))

    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        """
        Returns the block hash with the given number in the canonical chain.

        Raises BlockNotFound if there's no block with the given number in the
        canonical chain.
        """
        return self.chaindb.get_canonical_block_hash(block_number)

    def build_block_with_transactions(self, transactions, parent_header=None):
        """
        Generate a block with the provided transactions. This does *not* import
        that block into your chain. If you want this new block in your chain,
        run :meth:`~import_block` with the result block from this method.

        :param transactions: an iterable of transactions to insert to the block
        :param parent_header: parent of the new block -- or canonical head if ``None``
        :return: (new block, receipts, computations)
        """
        base_header = self.ensure_header(parent_header)
        vm = self.get_vm(base_header)

        new_header, receipts, computations = vm.apply_all_transactions(transactions, base_header)
        new_block = vm.set_block_transactions(vm.block, new_header, transactions, receipts)

        return new_block, receipts, computations

    #
    # Transaction API
    #
    def get_canonical_transaction(self, transaction_hash: Hash32) -> BaseTransaction:
        """
        Returns the requested transaction as specified by the transaction hash
        from the canonical chain.

        Raises TransactionNotFound if no transaction with the specified hash is
        found in the main chain.
        """
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

    def create_transaction(self, *args: Any, **kwargs: Any) -> BaseTransaction:
        """
        Passthrough helper to the current VM class.
        """
        return self.get_vm().create_transaction(*args, **kwargs)

    def create_unsigned_transaction(self,
                                    *args: Any,
                                    **kwargs: Any) -> BaseUnsignedTransaction:
        """
        Passthrough helper to the current VM class.
        """
        return self.get_vm().create_unsigned_transaction(*args, **kwargs)

    #
    # Execution API
    #
    def get_transaction_result(
            self,
            transaction: Union[BaseTransaction, SpoofTransaction],
            at_header: BlockHeader) -> bytes:
        """
        Return the result of running the given transaction.
        This is referred to as a `call()` in web3.
        """
        with self.get_vm(at_header).state_in_temp_block() as state:
            computation = state.costless_execute_transaction(transaction)

        computation.raise_if_error()
        return computation.output

    def estimate_gas(
            self,
            transaction: Union[BaseTransaction, SpoofTransaction],
            at_header: BlockHeader=None) -> int:
        """
        Returns an estimation of the amount of gas the given transaction will
        use if executed on top of the block specified by the given header.
        """
        if at_header is None:
            at_header = self.get_canonical_head()
        with self.get_vm(at_header).state_in_temp_block() as state:
            return self.gas_estimator(state, transaction)

    def import_block(self,
                     block: BaseBlock,
                     perform_validation: bool=True
                     ) -> Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]]:
        """
        Imports a complete block and returns a 3-tuple

        - the imported block
        - a tuple of blocks which are now part of the canonical chain.
        - a tuple of blocks which are were canonical and now are no longer canonical.
        """

        try:
            parent_header = self.get_block_header_by_hash(block.header.parent_hash)
        except HeaderNotFound:
            raise ValidationError(
                "Attempt to import block #{}.  Cannot import block {} before importing "
                "its parent block at {}".format(
                    block.number,
                    block.hash,
                    block.header.parent_hash,
                )
            )

        base_header_for_import = self.create_header_from_parent(parent_header)
        imported_block = self.get_vm(base_header_for_import).import_block(block)

        # Validate the imported block.
        if perform_validation:
            validate_imported_block_unchanged(imported_block, block)
            self.validate_block(imported_block)

        (
            new_canonical_hashes,
            old_canonical_hashes,
        ) = self.chaindb.persist_block(imported_block)

        self.logger.debug(
            'IMPORTED_BLOCK: number %s | hash %s',
            imported_block.number,
            encode_hex(imported_block.hash),
        )

        new_canonical_blocks = tuple(
            self.get_block_by_hash(header_hash)
            for header_hash
            in new_canonical_hashes
        )
        old_canonical_blocks = tuple(
            self.get_block_by_hash(header_hash)
            for header_hash
            in old_canonical_hashes
        )

        return imported_block, new_canonical_blocks, old_canonical_blocks

    #
    # Validation API
    #
    def validate_receipt(self, receipt: Receipt, at_header: BlockHeader) -> None:
        VM = self.get_vm_class(at_header)
        VM.validate_receipt(receipt)

    def validate_block(self, block: BaseBlock) -> None:
        """
        Performs validation on a block that is either being mined or imported.

        Since block validation (specifically the uncle validation) must have
        access to the ancestor blocks, this validation must occur at the Chain
        level.

        Cannot be used to validate genesis block.
        """
        if block.is_genesis:
            raise ValidationError("Cannot validate genesis block this way")
        VM = self.get_vm_class_for_block_number(BlockNumber(block.number))
        parent_block = self.get_block_by_hash(block.header.parent_hash)
        VM.validate_header(block.header, parent_block.header, check_seal=True)
        self.validate_uncles(block)
        self.validate_gaslimit(block.header)

    def validate_seal(self, header: BlockHeader) -> None:
        """
        Validate the seal on the given header.
        """
        VM = self.get_vm_class_for_block_number(BlockNumber(header.block_number))
        VM.validate_seal(header)

    def validate_gaslimit(self, header: BlockHeader) -> None:
        """
        Validate the gas limit on the given header.
        """
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

    def validate_uncles(self, block: BaseBlock) -> None:
        """
        Validate the uncles for the given block.
        """
        has_uncles = len(block.uncles) > 0
        should_have_uncles = block.header.uncles_hash != EMPTY_UNCLE_HASH

        if not has_uncles and not should_have_uncles:
            # optimization to avoid loading ancestors from DB, since the block has no uncles
            return
        elif has_uncles and not should_have_uncles:
            raise ValidationError("Block has uncles but header suggests uncles should be empty")
        elif should_have_uncles and not has_uncles:
            raise ValidationError("Header suggests block should have uncles but block has none")

        # Check for duplicates
        uncle_groups = groupby(operator.attrgetter('hash'), block.uncles)
        duplicate_uncles = tuple(sorted(
            hash for hash, twins in uncle_groups.items() if len(twins) > 1
        ))
        if duplicate_uncles:
            raise ValidationError(
                "Block contains duplicate uncles:\n"
                " - {0}".format(' - '.join(duplicate_uncles))
            )

        recent_ancestors = tuple(
            ancestor
            for ancestor
            in self.get_ancestors(MAX_UNCLE_DEPTH + 1, header=block.header)
        )
        recent_ancestor_hashes = {ancestor.hash for ancestor in recent_ancestors}
        recent_uncle_hashes = _extract_uncle_hashes(recent_ancestors)

        for uncle in block.uncles:
            if uncle.hash == block.hash:
                raise ValidationError("Uncle has same hash as block")

            # ensure the uncle has not already been included.
            if uncle.hash in recent_uncle_hashes:
                raise ValidationError(
                    "Duplicate uncle: {0}".format(encode_hex(uncle.hash))
                )

            # ensure that the uncle is not one of the canonical chain blocks.
            if uncle.hash in recent_ancestor_hashes:
                raise ValidationError(
                    "Uncle {0} cannot be an ancestor of {1}".format(
                        encode_hex(uncle.hash), encode_hex(block.hash)))

            # ensure that the uncle was built off of one of the canonical chain
            # blocks.
            if uncle.parent_hash not in recent_ancestor_hashes or (
               uncle.parent_hash == block.header.parent_hash):
                raise ValidationError(
                    "Uncle's parent {0} is not an ancestor of {1}".format(
                        encode_hex(uncle.parent_hash), encode_hex(block.hash)))

            # Now perform VM level validation of the uncle
            self.validate_seal(uncle)

            try:
                uncle_parent = self.get_block_header_by_hash(uncle.parent_hash)
            except HeaderNotFound:
                raise ValidationError(
                    "Uncle ancestor not found: {0}".format(uncle.parent_hash)
                )

            uncle_vm_class = self.get_vm_class_for_block_number(uncle.block_number)
            uncle_vm_class.validate_uncle(block, uncle, uncle_parent)

    def validate_chain(
            self,
            parent: BlockHeader,
            chain: Tuple[BlockHeader, ...],
            seal_check_random_sample_rate: int = 1) -> None:

        all_indices = list(range(len(chain)))
        if seal_check_random_sample_rate == 1:
            headers_to_check_seal = set(all_indices)
        else:
            sample_size = len(all_indices) // seal_check_random_sample_rate
            headers_to_check_seal = set(random.sample(all_indices, sample_size))

        for i, header in enumerate(chain):
            if header.parent_hash != parent.hash:
                raise ValidationError(
                    "Invalid header chain; {} has parent {}, but expected {}".format(
                        header, header.parent_hash, parent.hash))
            vm_class = self.get_vm_class_for_block_number(header.block_number)
            if i in headers_to_check_seal:
                vm_class.validate_header(header, parent, check_seal=True)
            else:
                vm_class.validate_header(header, parent, check_seal=False)
            parent = header


@to_set
def _extract_uncle_hashes(blocks):
    for block in blocks:
        for uncle in block.uncles:
            yield uncle.hash


class MiningChain(Chain):
    header = None  # type: BlockHeader

    def __init__(self, base_db: BaseAtomicDB, header: BlockHeader=None) -> None:
        super().__init__(base_db)
        self.header = self.ensure_header(header)

    def apply_transaction(self, transaction):
        """
        Applies the transaction to the current tip block.

        WARNING: Receipt and Transaction trie generation is computationally
        heavy and incurs significant perferomance overhead.
        """
        vm = self.get_vm(self.header)
        base_block = vm.block

        new_header, receipt, computation = vm.apply_transaction(base_block.header, transaction)

        # since we are building the block locally, we have to persist all the incremental state
        vm.state.account_db.persist()

        transactions = base_block.transactions + (transaction, )
        receipts = base_block.get_receipts(self.chaindb) + (receipt, )

        new_block = vm.set_block_transactions(base_block, new_header, transactions, receipts)

        self.header = new_block.header

        return new_block, receipt, computation

    def import_block(self,
                     block: BaseBlock,
                     perform_validation: bool=True
                     ) -> Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]]:
        imported_block, new_canonical_blocks, old_canonical_blocks = super().import_block(
            block, perform_validation)

        self.header = self.ensure_header()
        return imported_block, new_canonical_blocks, old_canonical_blocks

    def mine_block(self, *args: Any, **kwargs: Any) -> BaseBlock:
        """
        Mines the current block. Proxies to the current Virtual Machine.
        See VM. :meth:`~eth.vm.base.VM.mine_block`
        """
        mined_block = self.get_vm(self.header).mine_block(*args, **kwargs)

        self.validate_block(mined_block)

        self.chaindb.persist_block(mined_block)
        self.header = self.create_header_from_parent(mined_block.header)
        return mined_block

    def get_vm(self, at_header: BlockHeader=None) -> 'BaseVM':
        if at_header is None:
            at_header = self.header

        return super().get_vm(at_header)


# This class is a work in progress; its main purpose is to define the API of an asyncio-compatible
# Chain implementation.
class AsyncChain(Chain):
    # TODO: this really belongs in the `trinity` module.

    async def coro_import_block(self,
                                block: BlockHeader,
                                perform_validation: bool=True,
                                ) -> Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]]:
        raise NotImplementedError()

    async def coro_validate_chain(
            self,
            parent: BlockHeader,
            chain: Tuple[BlockHeader, ...],
            seal_check_random_sample_rate: int = 1) -> None:
        raise NotImplementedError()

    async def coro_validate_receipt(self,
                                    receipt: Receipt,
                                    at_header: BlockHeader) -> None:
        raise NotImplementedError()

    async def coro_get_block_by_hash(self,
                                     block_hash: Hash32) -> BaseBlock:
        raise NotImplementedError()

    async def coro_get_block_by_header(self,
                                       header: BlockHeader) -> BaseBlock:
        raise NotImplementedError()

    async def coro_get_canonical_block_by_number(self,
                                                 block_number: BlockNumber) -> BaseBlock:
        raise NotImplementedError()
