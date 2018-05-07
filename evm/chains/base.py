from __future__ import absolute_import

from abc import (
    ABCMeta,
    abstractmethod
)
from typing import (  # noqa: F401
    Any,
    Optional,
    Callable,
    cast,
    Dict,
    Generator,
    Iterator,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)

import logging

from cytoolz import (
    assoc,
)

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
)

from eth_utils import (
    to_tuple,
)

from evm.db.chain import BaseChainDB
from evm.consensus.pow import (
    check_pow,
)
from evm.constants import (
    BLANK_ROOT_HASH,
    MAX_UNCLE_DEPTH,
)
from evm.estimators import (
    get_gas_estimator,
)
from evm.exceptions import (
    HeaderNotFound,
    TransactionNotFound,
    ValidationError,
    VMNotFound,
)
from evm.validation import (
    validate_block_number,
    validate_uint256,
    validate_word,
    validate_vm_configuration,
)
from evm.rlp.blocks import (
    BaseBlock,
)
from evm.rlp.headers import (
    BlockHeader,
    HeaderParams,
)
from evm.rlp.transactions import (
    BaseTransaction,
    BaseUnsignedTransaction,
)
from evm.utils.db import (
    apply_state_dict,
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

if TYPE_CHECKING:
    from evm.vm.base import BaseVM  # noqa: F401


# Mapping from address to account state.
# 'balance', 'nonce' -> int
# 'code' -> bytes
# 'storage' -> Dict[int, int]
AccountState = Dict[Address, Dict[str, Union[int, bytes, Dict[int, int]]]]


class BaseChain(Configurable, metaclass=ABCMeta):
    """
    The base class for all Chain objects
    """
    chaindb = None  # type: BaseChainDB

    #
    # Chain API
    #
    @classmethod
    @abstractmethod
    def from_genesis(cls,
                     chaindb: BaseChainDB,
                     genesis_params: Dict[str, HeaderParams],
                     genesis_state: AccountState=None) -> 'BaseChain':
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    @abstractmethod
    def from_genesis_header(cls,
                            chaindb: BaseChainDB,
                            genesis_header: BlockHeader) -> 'BaseChain':
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_chain_at_block_parent(self, block: BaseBlock) -> 'BaseChain':
        raise NotImplementedError("Chain classes must implement this method")

    #
    # VM API
    #
    @abstractmethod
    def get_vm(self, header: BlockHeader=None) -> 'BaseVM':
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_vm_class_for_block_number(self, block_number: BlockNumber) -> Type['BaseVM']:
        raise NotImplementedError("Chain classes must implement this method")

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

    #
    # Block API
    #
    def get_ancestors(self, limit: int) -> Iterator[BaseBlock]:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_block(self) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")

    def get_block_by_hash(self, block_hash: Hash32) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")

    def get_block_by_header(self, block_header: BlockHeader) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_canonical_block_by_number(self, block_number: BlockNumber) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_canonical_block_hash(self, block_number):
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
    def apply_transaction(self, transaction):
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def estimate_gas(self, transaction: BaseTransaction, at_header: BlockHeader=None) -> int:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def import_block(self, block: BaseBlock, perform_validation: bool=True) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def mine_block(self, *args: Any, **kwargs: Any) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Validation API
    #
    @abstractmethod
    def validate_block(self, block: BaseBlock) -> None:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def validate_gaslimit(self, header: BlockHeader) -> None:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def validate_seal(self, header: BlockHeader) -> None:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def validate_uncles(self, block: BaseBlock) -> None:
        raise NotImplementedError("Chain classes must implement this method")


class Chain(BaseChain):
    """
    A Chain is a combination of one or more VM classes.  Each VM is associated
    with a range of blocks.  The Chain class acts as a wrapper around these other
    VM classes, delegating operations to the appropriate VM depending on the
    current block number.
    """
    logger = logging.getLogger("evm.chain.chain.Chain")
    header = None  # type: BlockHeader
    network_id = None  # type: int
    vm_configuration = None  # type: Tuple[Tuple[int, Type[BaseVM]], ...]
    gas_estimator = None  # type: Callable

    def __init__(self, chaindb: BaseChainDB, header: BlockHeader=None) -> None:
        if not self.vm_configuration:
            raise ValueError(
                "The Chain class cannot be instantiated with an empty `vm_configuration`"
            )
        else:
            validate_vm_configuration(self.vm_configuration)

        self.chaindb = chaindb
        self.header = header
        if self.header is None:
            self.header = self.create_header_from_parent(self.get_canonical_head())
        if self.gas_estimator is None:
            self.gas_estimator = get_gas_estimator()  # type: ignore

    #
    # Chain API
    #
    @classmethod
    def from_genesis(cls,
                     chaindb: BaseChainDB,
                     genesis_params: Dict[str, HeaderParams],
                     genesis_state: AccountState=None) -> 'BaseChain':
        """
        Initializes the Chain from a genesis state.
        """
        genesis_vm_class = cls.get_vm_class_for_block_number(BlockNumber(0))
        account_db = genesis_vm_class.get_state_class().get_account_db_class()(
            chaindb.db,
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
        genesis_chain = cls(chaindb, genesis_header)
        chaindb.persist_block(genesis_chain.get_block())
        return cls.from_genesis_header(chaindb, genesis_header)

    @classmethod
    def from_genesis_header(cls,
                            chaindb: BaseChainDB,
                            genesis_header: BlockHeader) -> 'BaseChain':
        """
        Initializes the chain from the genesis header.
        """
        chaindb.persist_header(genesis_header)
        return cls(chaindb)

    def get_chain_at_block_parent(self, block: BaseBlock) -> BaseChain:
        """
        Returns a `Chain` instance with the given block's parent at the chain head.
        """
        try:
            parent_header = self.get_block_header_by_hash(block.header.parent_hash)
        except HeaderNotFound:
            raise ValidationError("Parent ({0}) of block {1} not found".format(
                block.header.parent_hash,
                block.header.hash
            ))

        init_header = self.create_header_from_parent(parent_header)
        return type(self)(self.chaindb, init_header)

    #
    # VM API
    #
    def get_vm(self, header: BlockHeader=None) -> 'BaseVM':
        """
        Returns the VM instance for the given block number.
        """
        if header is None:
            header = self.header

        vm_class = self.get_vm_class_for_block_number(header.block_number)
        return vm_class(header=header, chaindb=self.chaindb)

    @classmethod
    def get_vm_class_for_block_number(cls, block_number: BlockNumber) -> Type['BaseVM']:
        """
        Returns the VM class for the given block number.
        """
        validate_block_number(block_number)
        for start_block, vm_class in reversed(cls.vm_configuration):
            if block_number >= start_block:
                return vm_class
        else:
            raise VMNotFound("No vm available for block #{0}".format(block_number))

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

    #
    # Block API
    #
    @to_tuple
    def get_ancestors(self, limit: int) -> Iterator[BaseBlock]:
        """
        Return `limit` number of ancestor blocks from the current canonical head.
        """
        lower_limit = max(self.header.block_number - limit, 0)
        for n in reversed(range(lower_limit, self.header.block_number)):
            yield self.get_canonical_block_by_number(BlockNumber(n))

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
    def apply_transaction(self, transaction):
        """
        Applies the transaction to the current tip block.

        WARNING: Receipt and Transaction trie generation is computationally
        heavy and incurs significant perferomance overhead.
        """
        vm = self.get_vm()
        base_block = vm.block

        new_header, receipt, computation = vm.apply_transaction(base_block.header, transaction)

        transactions = base_block.transactions + (transaction, )
        receipts = base_block.get_receipts(self.chaindb) + (receipt, )

        new_block = vm.set_block_transactions(base_block, new_header, transactions, receipts)

        self.header = new_block.header

        return new_block, receipt, computation

    def estimate_gas(self, transaction: BaseTransaction, at_header: BlockHeader=None) -> int:
        """
        Returns an estimation of the amount of gas the given transaction will
        use if executed on top of the block specified by the given header.
        """
        if at_header is None:
            at_header = self.get_canonical_head()
        with self.get_vm(at_header).state_in_temp_block() as state:
            return self.gas_estimator(state, transaction)

    def import_block(self, block: BaseBlock, perform_validation: bool=True) -> BaseBlock:
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

    def mine_block(self, *args: Any, **kwargs: Any) -> BaseBlock:
        """
        Mines the current block. Proxies to the current Virtual Machine.
        See VM. :meth:`~evm.vm.base.VM.mine_block`
        """
        mined_block = self.get_vm().mine_block(*args, **kwargs)

        self.validate_block(mined_block)

        self.chaindb.persist_block(mined_block)
        self.header = self.create_header_from_parent(self.get_canonical_head())
        return mined_block

    #
    # Validation API
    #
    def validate_block(self, block: BaseBlock) -> None:
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

    def validate_seal(self, header: BlockHeader) -> None:
        """
        Validate the seal on the given header.
        """
        check_pow(
            header.block_number, header.mining_hash,
            header.mix_hash, header.nonce, header.difficulty)

    def validate_uncles(self, block: BaseBlock) -> None:
        """
        Validate the uncles for the given block.
        """
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


# This class is a work in progress; its main purpose is to define the API of an asyncio-compatible
# Chain implementation.
class AsyncChain(Chain):

    async def coro_import_block(self,
                                block: BlockHeader,
                                perform_validation: bool=True) -> BaseBlock:
        raise NotImplementedError()
