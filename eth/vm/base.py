from __future__ import absolute_import
from abc import (
    ABC,
    abstractmethod,
)
import contextlib
import itertools
import logging
from typing import (
    Any,
    Iterable,
    Iterator,
    Optional,
    Tuple,
    Type,
)

from typing import Set

from eth_hash.auto import keccak
from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    decode_hex,
    ValidationError,
)
import rlp

from eth.consensus.pow import (
    check_pow,
)
from eth.constants import (
    GENESIS_PARENT_HASH,
    MAX_PREV_HEADER_DEPTH,
    MAX_UNCLES,
)
from eth.db.backends.base import (
    BaseAtomicDB,
)
from eth.db.trie import make_trie_root_and_nodes
from eth.db.chain import BaseChainDB
from eth.db.schema import Schemas
from eth.exceptions import (
    HeaderNotFound,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.rlp.receipts import Receipt
from eth.rlp.sedes import (
    uint32,
)
from eth.rlp.transactions import (
    BaseTransaction,
    BaseUnsignedTransaction,
)
from eth._utils.datatypes import (
    Configurable,
)
from eth._utils.db import (
    get_parent_header,
    get_block_header_by_hash,
)
from eth._utils.headers import (
    generate_header_from_parent_header,
)
from eth.validation import (
    validate_length_lte,
    validate_gas_limit,
)
from eth.vm.interrupt import (
    EVMMissingData,
)
from eth.vm.message import (
    Message,
)
from eth.vm.state import BaseState
from eth.vm.computation import BaseComputation


class BaseVM(Configurable, ABC):
    block_class: Type[BaseBlock] = None
    fork: str = None  # noqa: E701  # flake8 bug that's fixed in 3.6.0+
    chaindb: BaseChainDB = None
    _state_class: Type[BaseState] = None

    @abstractmethod
    def __init__(self, header: BlockHeader, chaindb: BaseChainDB) -> None:
        pass

    @property
    @abstractmethod
    def state(self) -> BaseState:
        pass

    @classmethod
    @abstractmethod
    def build_state(cls,
                    db: BaseAtomicDB,
                    header: BlockHeader,
                    previous_hashes: Iterable[Hash32] = ()
                    ) -> BaseState:
        pass

    @abstractmethod
    def get_header(self) -> BlockHeader:
        pass

    @abstractmethod
    def get_block(self) -> BaseBlock:
        pass

    #
    # Logging
    #
    @property
    @abstractmethod
    def logger(self) -> logging.Logger:
        raise NotImplementedError("VM classes must implement this method")

    #
    # Execution
    #
    @abstractmethod
    def apply_transaction(self,
                          header: BlockHeader,
                          transaction: BaseTransaction
                          ) -> Tuple[Receipt, BaseComputation]:
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def execute_bytecode(self,
                         origin: Address,
                         gas_price: int,
                         gas: int,
                         to: Address,
                         sender: Address,
                         value: int,
                         data: bytes,
                         code: bytes,
                         code_address: Address = None) -> BaseComputation:
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def apply_all_transactions(
        self,
        transactions: Tuple[BaseTransaction, ...],
        base_header: BlockHeader
    ) -> Tuple[BlockHeader, Tuple[Receipt, ...], Tuple[BaseComputation, ...]]:
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def make_receipt(self,
                     base_header: BlockHeader,
                     transaction: BaseTransaction,
                     computation: BaseComputation,
                     state: BaseState) -> Receipt:
        """
        Generate the receipt resulting from applying the transaction.

        :param base_header: the header of the block before the transaction was applied.
        :param transaction: the transaction used to generate the receipt
        :param computation: the result of running the transaction computation
        :param state: the resulting state, after executing the computation

        :return: receipt
        """
        raise NotImplementedError("VM classes must implement this method")

    #
    # Mining
    #
    @abstractmethod
    def import_block(self, block: BaseBlock) -> BaseBlock:
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def mine_block(self, *args: Any, **kwargs: Any) -> BaseBlock:
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def set_block_transactions(self,
                               base_block: BaseBlock,
                               new_header: BlockHeader,
                               transactions: Tuple[BaseTransaction, ...],
                               receipts: Tuple[Receipt, ...]) -> BaseBlock:
        raise NotImplementedError("VM classes must implement this method")

    #
    # Finalization
    #
    @abstractmethod
    def finalize_block(self, block: BaseBlock) -> BaseBlock:
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def pack_block(self, block: BaseBlock, *args: Any, **kwargs: Any) -> BaseBlock:
        raise NotImplementedError("VM classes must implement this method")

    #
    # Headers
    #
    @abstractmethod
    def add_receipt_to_header(self, old_header: BlockHeader, receipt: Receipt) -> BlockHeader:
        """
        Apply the receipt to the old header, and return the resulting header. This may have
        storage-related side-effects. For example, pre-Byzantium, the state root hash
        is included in the receipt, and so must be stored into the database.
        """
        pass

    @classmethod
    @abstractmethod
    def compute_difficulty(cls, parent_header: BlockHeader, timestamp: int) -> int:
        """
        Compute the difficulty for a block header.

        :param parent_header: the parent header
        :param timestamp: the timestamp of the child header
        """
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def configure_header(self, **header_params: Any) -> BlockHeader:
        """
        Setup the current header with the provided parameters.  This can be
        used to set fields like the gas limit or timestamp to value different
        than their computed defaults.
        """
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def create_header_from_parent(cls,
                                  parent_header: BlockHeader,
                                  **header_params: Any) -> BlockHeader:
        """
        Creates and initializes a new block header from the provided
        `parent_header`.
        """
        raise NotImplementedError("VM classes must implement this method")

    #
    # Blocks
    #
    @classmethod
    @abstractmethod
    def generate_block_from_parent_header_and_coinbase(cls,
                                                       parent_header: BlockHeader,
                                                       coinbase: Address) -> BaseBlock:
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def get_block_class(cls) -> Type[BaseBlock]:
        raise NotImplementedError("VM classes must implement this method")

    @staticmethod
    @abstractmethod
    def get_block_reward() -> int:
        """
        Return the amount in **wei** that should be given to a miner as a reward
        for this block.

          .. note::
            This is an abstract method that must be implemented in subclasses
        """
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def get_nephew_reward(cls) -> int:
        """
        Return the reward which should be given to the miner of the given `nephew`.

          .. note::
            This is an abstract method that must be implemented in subclasses
        """
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def get_prev_hashes(cls,
                        last_block_hash: Hash32,
                        chaindb: BaseChainDB) -> Optional[Iterable[Hash32]]:
        raise NotImplementedError("VM classes must implement this method")

    @staticmethod
    @abstractmethod
    def get_uncle_reward(block_number: int, uncle: BaseBlock) -> int:
        """
        Return the reward which should be given to the miner of the given `uncle`.

          .. note::
            This is an abstract method that must be implemented in subclasses
        """
        raise NotImplementedError("VM classes must implement this method")

    #
    # Transactions
    #
    @abstractmethod
    def create_transaction(self, *args: Any, **kwargs: Any) -> BaseTransaction:
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> BaseUnsignedTransaction:
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def get_transaction_class(cls) -> Type[BaseTransaction]:
        raise NotImplementedError("VM classes must implement this method")

    #
    # Validate
    #
    @classmethod
    @abstractmethod
    def validate_receipt(self, receipt: Receipt) -> None:
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def validate_block(self, block: BaseBlock) -> None:
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def validate_header(cls,
                        header: BlockHeader,
                        parent_header: BlockHeader,
                        check_seal: bool = True
                        ) -> None:
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def validate_transaction_against_header(self,
                                            base_header: BlockHeader,
                                            transaction: BaseTransaction) -> None:
        """
        Validate that the given transaction is valid to apply to the given header.

        :param base_header: header before applying the transaction
        :param transaction: the transaction to validate

        :raises: ValidationError if the transaction is not valid to apply
        """
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def validate_seal(cls, header: BlockHeader) -> None:
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def validate_uncle(cls,
                       block: BaseBlock,
                       uncle: BlockHeader,
                       uncle_parent: BlockHeader
                       ) -> None:
        raise NotImplementedError("VM classes must implement this method")

    #
    # State
    #
    @classmethod
    @abstractmethod
    def get_state_class(cls) -> Type[BaseState]:
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    @contextlib.contextmanager
    def state_in_temp_block(self) -> Iterator[BaseState]:
        raise NotImplementedError("VM classes must implement this method")


class VM(BaseVM):
    cls_logger = logging.getLogger('eth.vm.base.VM')
    """
    The :class:`~eth.vm.base.BaseVM` class represents the Chain rules for a
    specific protocol definition such as the Frontier or Homestead network.

      .. note::

        Each :class:`~eth.vm.base.BaseVM` class must be configured with:

        - ``block_class``: The :class:`~eth.rlp.blocks.Block` class for blocks in this VM ruleset.
        - ``_state_class``: The :class:`~eth.vm.state.State` class used by this VM for execution.
    """

    _state = None
    _block = None

    def __init__(self, header: BlockHeader, chaindb: BaseChainDB) -> None:
        self.chaindb = chaindb
        self._initial_header = header

    def get_header(self) -> BlockHeader:
        if self._block is None:
            return self._initial_header
        else:
            return self._block.header

    def get_block(self) -> BaseBlock:
        if self._block is None:
            block_class = self.get_block_class()
            self._block = block_class.from_header(header=self._initial_header, chaindb=self.chaindb)
        return self._block

    @property
    def state(self) -> BaseState:
        if self._state is None:
            self._state = self.build_state(self.chaindb.db, self.get_header(), self.previous_hashes)
        return self._state

    @classmethod
    def build_state(cls,
                    db: BaseAtomicDB,
                    header: BlockHeader,
                    previous_hashes: Iterable[Hash32] = (),
                    expected_schema: Schemas = Schemas.TURBO,
                    ) -> BaseState:
        """
        You probably want `VM().state` instead of this.

        Occasionally, you want to build custom state against a particular header and DB,
        even if you don't have the VM initialized. This is a convenience method to do that.
        """

        execution_context = header.create_execution_context(previous_hashes)
        return cls.get_state_class()(
            db, execution_context, header, expected_schema
        )

    #
    # Logging
    #
    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger('eth.vm.base.VM.{0}'.format(self.__class__.__name__))

    #
    # Execution
    #
    def apply_transaction(self,
                          header: BlockHeader,
                          transaction: BaseTransaction
                          ) -> Tuple[Receipt, BaseComputation]:
        """
        Apply the transaction to the current block. This is a wrapper around
        :func:`~eth.vm.state.State.apply_transaction` with some extra orchestration logic.

        :param header: header of the block before application
        :param transaction: to apply
        """
        self.validate_transaction_against_header(header, transaction)
        computation = self.state.apply_transaction(transaction)
        receipt = self.make_receipt(header, transaction, computation, self.state)
        self.validate_receipt(receipt)

        return receipt, computation

    def execute_bytecode(self,
                         origin: Address,
                         gas_price: int,
                         gas: int,
                         to: Address,
                         sender: Address,
                         value: int,
                         data: bytes,
                         code: bytes,
                         code_address: Address = None,
                         ) -> BaseComputation:
        """
        Execute raw bytecode in the context of the current state of
        the virtual machine.
        """
        if origin is None:
            origin = sender

        # Construct a message
        message = Message(
            gas=gas,
            to=to,
            sender=sender,
            value=value,
            data=data,
            code=code,
            code_address=code_address,
        )

        # Construction a tx context
        transaction_context = self.state.get_transaction_context_class()(
            gas_price=gas_price,
            origin=origin,
        )

        # Execute it in the VM
        return self.state.get_computation(message, transaction_context).apply_computation(
            self.state,
            message,
            transaction_context,
        )

    def apply_all_transactions(
        self,
        transactions: Tuple[BaseTransaction, ...],
        base_header: BlockHeader
    ) -> Tuple[BlockHeader, Tuple[Receipt, ...], Tuple[BaseComputation, ...]]:
        """
        Determine the results of applying all transactions to the base header.
        This does *not* update the current block or header of the VM.

        :param transactions: an iterable of all transactions to apply
        :param base_header: the starting header to apply transactions to
        :return: the final header, the receipts of each transaction, and the computations
        """
        if base_header.block_number != self.get_header().block_number:
            raise ValidationError(
                "This VM instance must only work on block #{}, "
                "but the target header has block #{}".format(
                    self.get_header().block_number,
                    base_header.block_number,
                )
            )

        receipts = []
        computations = []
        previous_header = base_header
        result_header = base_header

        for transaction in transactions:
            try:
                snapshot = self.state.snapshot()
                receipt, computation = self.apply_transaction(
                    previous_header,
                    transaction,
                )
            except EVMMissingData as exc:
                self.state.revert(snapshot)

            result_header = self.add_receipt_to_header(previous_header, receipt)
            previous_header = result_header
            receipts.append(receipt)
            computations.append(computation)

        receipts_tuple = tuple(receipts)
        computations_tuple = tuple(computations)

        return result_header, receipts_tuple, computations_tuple

    #
    # Mining
    #
    def import_block(self, block: BaseBlock) -> BaseBlock:
        """
        Import the given block to the chain.
        """
        if self.get_block().number != block.number:
            raise ValidationError(
                "This VM can only import blocks at number #{}, the attempted block was #{}".format(
                    self.get_block().number,
                    block.number,
                )
            )

        self._block = self.get_block().copy(
            header=self.configure_header(
                coinbase=block.header.coinbase,
                gas_limit=block.header.gas_limit,
                timestamp=block.header.timestamp,
                extra_data=block.header.extra_data,
                mix_hash=block.header.mix_hash,
                nonce=block.header.nonce,
                uncles_hash=keccak(rlp.encode(block.uncles)),
            ),
            uncles=block.uncles,
        )

        # we need to re-initialize the `state` to update the execution context.
        header = self.get_header()
        parent_header_hash = header.parent_hash
        parent_header = self.chaindb.get_block_header_by_hash(parent_header_hash)
        execution_context = header.create_execution_context(self.previous_hashes)
        self._state = self.get_state_class()(
            self.chaindb.db, execution_context, parent_header, Schemas.TURBO,
        )

        # In geth the state is modified for the DAO fork block before any transactions are
        # applied. Doing it here is the closest we can get to that.
        block_number = header.block_number
        supports_dao_fork = hasattr(self, 'support_dao_fork') and self.support_dao_fork
        if supports_dao_fork and block_number == self.get_dao_fork_block_number():

            for hex_account in dao_drain_list:
                address = Address(decode_hex(hex_account))
                balance = self._state.get_balance(address)
                self._state.delta_balance(dao_refund_contract, balance)
                self._state.set_balance(address, 0)

            # Persist the changes to the database
            self._state.persist()

            base_header = header.copy(
                state_root=self._state.state_root
            )
        else:
            base_header = header

        # run all of the transactions.
        new_header, receipts, _ = self.apply_all_transactions(
            block.transactions, base_header
        )

        self._block = self.set_block_transactions(
            self.get_block(),
            new_header,
            block.transactions,
            receipts,
        )

        return self.mine_block()

    def mine_block(self, *args: Any, **kwargs: Any) -> BaseBlock:
        """
        Mine the current block. Proxies to self.pack_block method.
        """
        packed_block = self.pack_block(self.get_block(), *args, **kwargs)

        final_block = self.finalize_block(packed_block)

        # Perform validation
        self.validate_block(final_block)

        return final_block

    def set_block_transactions(self,
                               base_block: BaseBlock,
                               new_header: BlockHeader,
                               transactions: Tuple[BaseTransaction, ...],
                               receipts: Tuple[Receipt, ...]) -> BaseBlock:

        tx_root_hash, tx_kv_nodes = make_trie_root_and_nodes(transactions)
        self.chaindb.persist_trie_data_dict(tx_kv_nodes)

        receipt_root_hash, receipt_kv_nodes = make_trie_root_and_nodes(receipts)
        self.chaindb.persist_trie_data_dict(receipt_kv_nodes)

        return base_block.copy(
            transactions=transactions,
            header=new_header.copy(
                transaction_root=tx_root_hash,
                receipt_root=receipt_root_hash,
            ),
        )

    #
    # Finalization
    #
    def _assign_block_rewards(self, block: BaseBlock) -> None:
        block_reward = self.get_block_reward() + (
            len(block.uncles) * self.get_nephew_reward()
        )

        self.state.delta_balance(block.header.coinbase, block_reward)
        self.logger.debug(
            "BLOCK REWARD: %s -> %s",
            block_reward,
            block.header.coinbase,
        )

        for uncle in block.uncles:
            uncle_reward = self.get_uncle_reward(block.number, uncle)
            self.state.delta_balance(uncle.coinbase, uncle_reward)
            self.logger.debug(
                "UNCLE REWARD REWARD: %s -> %s",
                uncle_reward,
                uncle.coinbase,
            )

    def finalize_block(self, block: BaseBlock) -> BaseBlock:
        """
        Perform any finalization steps like awarding the block mining reward,
        and persisting the final state root.
        """
        if block.number > 0:
            snapshot = self.state.snapshot()
            try:
                self._assign_block_rewards(block)
            except EVMMissingData as exc:
                self.state.revert(snapshot)
                raise
            else:
                self.state.commit(snapshot)

        # We need to call `persist` here since the state db batches
        # all writes until we tell it to write to the underlying db
        # self.state.persist()

        # TODO: only do this if we're in turbo mode
        # TODO: will we always know the hash here?
        parent_hash = block.header.parent_hash
        parent_header = self.chaindb.get_block_header_by_hash(parent_hash)
        block_diff = self.state.persist_returning_block_diff(parent_header.state_root)

        result = block.copy(header=block.header.copy(state_root=self.state.state_root))

        basedb = self.chaindb.db
        block_diff.write_to(basedb, result.header.state_root)
        return result

    def pack_block(self, block: BaseBlock, *args: Any, **kwargs: Any) -> BaseBlock:
        """
        Pack block for mining.

        :param bytes coinbase: 20-byte public address to receive block reward
        :param bytes uncles_hash: 32 bytes
        :param bytes state_root: 32 bytes
        :param bytes transaction_root: 32 bytes
        :param bytes receipt_root: 32 bytes
        :param int bloom:
        :param int gas_used:
        :param bytes extra_data: 32 bytes
        :param bytes mix_hash: 32 bytes
        :param bytes nonce: 8 bytes
        """
        if 'uncles' in kwargs:
            uncles = kwargs.pop('uncles')
            kwargs.setdefault('uncles_hash', keccak(rlp.encode(uncles)))
        else:
            uncles = block.uncles

        provided_fields = set(kwargs.keys())
        known_fields = set(BlockHeader._meta.field_names)
        unknown_fields = provided_fields.difference(known_fields)

        if unknown_fields:
            raise AttributeError(
                "Unable to set the field(s) {0} on the `BlockHeader` class. "
                "Received the following unexpected fields: {1}.".format(
                    ", ".join(known_fields),
                    ", ".join(unknown_fields),
                )
            )

        header = block.header.copy(**kwargs)
        packed_block = block.copy(uncles=uncles, header=header)

        return packed_block

    #
    # Blocks
    #
    @classmethod
    def generate_block_from_parent_header_and_coinbase(cls,
                                                       parent_header: BlockHeader,
                                                       coinbase: Address) -> BaseBlock:
        """
        Generate block from parent header and coinbase.
        """
        block_header = generate_header_from_parent_header(
            cls.compute_difficulty,
            parent_header,
            coinbase,
            timestamp=parent_header.timestamp + 1,
        )
        block = cls.get_block_class()(
            block_header,
            transactions=[],
            uncles=[],
        )
        return block

    @classmethod
    def get_block_class(cls) -> Type[BaseBlock]:
        """
        Return the :class:`~eth.rlp.blocks.Block` class that this VM uses for blocks.
        """
        if cls.block_class is None:
            raise AttributeError("No `block_class` has been set for this VM")
        else:
            return cls.block_class

    @classmethod
    def get_prev_hashes(cls,
                        last_block_hash: Hash32,
                        chaindb: BaseChainDB) -> Optional[Iterable[Hash32]]:
        if last_block_hash == GENESIS_PARENT_HASH:
            return

        block_header = get_block_header_by_hash(last_block_hash, chaindb)

        for _ in range(MAX_PREV_HEADER_DEPTH):
            yield block_header.hash
            try:
                block_header = get_parent_header(block_header, chaindb)
            except (IndexError, HeaderNotFound):
                break

    @property
    def previous_hashes(self) -> Optional[Iterable[Hash32]]:
        """
        Convenience API for accessing the previous 255 block hashes.
        """
        return self.get_prev_hashes(self.get_header().parent_hash, self.chaindb)

    #
    # Transactions
    #
    def create_transaction(self, *args: Any, **kwargs: Any) -> BaseTransaction:
        """
        Proxy for instantiating a signed transaction for this VM.
        """
        return self.get_transaction_class()(*args, **kwargs)

    @classmethod
    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> 'BaseUnsignedTransaction':
        """
        Proxy for instantiating an unsigned transaction for this VM.
        """
        return cls.get_transaction_class().create_unsigned_transaction(
            nonce=nonce,
            gas_price=gas_price,
            gas=gas,
            to=to,
            value=value,
            data=data
        )

    @classmethod
    def get_transaction_class(cls) -> Type[BaseTransaction]:
        """
        Return the class that this VM uses for transactions.
        """
        return cls.get_block_class().get_transaction_class()

    #
    # Validate
    #
    @classmethod
    def validate_receipt(cls, receipt: Receipt) -> None:
        already_checked: Set[Hash32] = set()

        for log_idx, log in enumerate(receipt.logs):
            if log.address in already_checked:
                continue
            elif log.address not in receipt.bloom_filter:
                raise ValidationError(
                    "The address from the log entry at position {0} is not "
                    "present in the provided bloom filter.".format(log_idx)
                )
            already_checked.add(log.address)

        for log_idx, log in enumerate(receipt.logs):
            for topic_idx, topic in enumerate(log.topics):
                if topic in already_checked:
                    continue
                elif uint32.serialize(topic) not in receipt.bloom_filter:
                    raise ValidationError(
                        "The topic at position {0} from the log entry at "
                        "position {1} is not present in the provided bloom "
                        "filter.".format(topic_idx, log_idx)
                    )
                already_checked.add(topic)

    def validate_block(self, block: BaseBlock) -> None:
        """
        Validate the the given block.
        """
        if not isinstance(block, self.get_block_class()):
            raise ValidationError(
                "This vm ({0!r}) is not equipped to validate a block of type {1!r}".format(
                    self,
                    block,
                )
            )

        if block.is_genesis:
            validate_length_lte(block.header.extra_data, 32, title="BlockHeader.extra_data")
        else:
            parent_header = get_parent_header(block.header, self.chaindb)
            self.validate_header(block.header, parent_header)

        tx_root_hash, _ = make_trie_root_and_nodes(block.transactions)
        if tx_root_hash != block.header.transaction_root:
            raise ValidationError(
                "Block's transaction_root ({0}) does not match expected value: {1}".format(
                    block.header.transaction_root, tx_root_hash))

        if len(block.uncles) > MAX_UNCLES:
            raise ValidationError(
                "Blocks may have a maximum of {0} uncles.  Found "
                "{1}.".format(MAX_UNCLES, len(block.uncles))
            )

        if not self.chaindb.exists(block.header.state_root):
            raise ValidationError(
                "`state_root` was not found in the db.\n"
                "- state_root: {0}".format(
                    block.header.state_root,
                )
            )
        local_uncle_hash = keccak(rlp.encode(block.uncles))
        if local_uncle_hash != block.header.uncles_hash:
            raise ValidationError(
                "`uncles_hash` and block `uncles` do not match.\n"
                " - num_uncles       : {0}\n"
                " - block uncle_hash : {1}\n"
                " - header uncle_hash: {2}".format(
                    len(block.uncles),
                    local_uncle_hash,
                    block.header.uncles_hash,
                )
            )

    @classmethod
    def validate_header(cls,
                        header: BlockHeader,
                        parent_header: BlockHeader,
                        check_seal: bool = True) -> None:
        """
        :raise eth.exceptions.ValidationError: if the header is not valid
        """
        if parent_header is None:
            # to validate genesis header, check if it equals canonical header at block number 0
            raise ValidationError("Must have access to parent header to validate current header")
        else:
            validate_length_lte(header.extra_data, 32, title="BlockHeader.extra_data")

            validate_gas_limit(header.gas_limit, parent_header.gas_limit)

            if header.block_number != parent_header.block_number + 1:
                raise ValidationError(
                    "Blocks must be numbered consecutively. Block number #{} has parent #{}".format(
                        header.block_number,
                        parent_header.block_number,
                    )
                )

            # timestamp
            if header.timestamp <= parent_header.timestamp:
                raise ValidationError(
                    "timestamp must be strictly later than parent, but is {} seconds before.\n"
                    "- child  : {}\n"
                    "- parent : {}. ".format(
                        parent_header.timestamp - header.timestamp,
                        header.timestamp,
                        parent_header.timestamp,
                    )
                )

            if check_seal:
                try:
                    cls.validate_seal(header)
                except ValidationError:
                    cls.cls_logger.warning(
                        "Failed to validate header proof of work on header: %r",
                        header.as_dict()
                    )
                    raise

    @classmethod
    def validate_seal(cls, header: BlockHeader) -> None:
        """
        Validate the seal on the given header.
        """
        check_pow(
            header.block_number, header.mining_hash,
            header.mix_hash, header.nonce, header.difficulty)

    @classmethod
    def validate_uncle(cls, block: BaseBlock, uncle: BaseBlock, uncle_parent: BaseBlock) -> None:
        """
        Validate the given uncle in the context of the given block.
        """
        if uncle.block_number >= block.number:
            raise ValidationError(
                "Uncle number ({0}) is higher than block number ({1})".format(
                    uncle.block_number, block.number))

        if uncle.block_number != uncle_parent.block_number + 1:
            raise ValidationError(
                "Uncle number ({0}) is not one above ancestor's number ({1})".format(
                    uncle.block_number, uncle_parent.block_number))
        if uncle.timestamp < uncle_parent.timestamp:
            raise ValidationError(
                "Uncle timestamp ({0}) is before ancestor's timestamp ({1})".format(
                    uncle.timestamp, uncle_parent.timestamp))
        if uncle.gas_used > uncle.gas_limit:
            raise ValidationError(
                "Uncle's gas usage ({0}) is above the limit ({1})".format(
                    uncle.gas_used, uncle.gas_limit))

    #
    # State
    #
    @classmethod
    def get_state_class(cls) -> Type[BaseState]:
        """
        Return the class that this VM uses for states.
        """
        if cls._state_class is None:
            raise AttributeError("No `_state_class` has been set for this VM")

        return cls._state_class

    @contextlib.contextmanager
    def state_in_temp_block(self) -> Iterator[BaseState]:
        snapshot = self.state.snapshot()
        yield self.state
        self.state.revert(snapshot)

        # header = self.get_header()
        # temp_block = self.generate_block_from_parent_header_and_coinbase(header, header.coinbase)
        # prev_hashes = itertools.chain((header.hash,), self.previous_hashes)

        # state = self.build_state(self.chaindb.db, temp_block.header, prev_hashes)

        # snapshot = state.snapshot()
        # yield state
        # state.revert(snapshot)


dao_refund_contract = Address(decode_hex('0xbf4ed7b27f1d666546e30d74d50d173d20bca754'))
dao_drain_list = [
    "0xd4fe7bc31cedb7bfb8a345f31e668033056b2728",
    "0xb3fb0e5aba0e20e5c49d252dfd30e102b171a425",
    "0x2c19c7f9ae8b751e37aeb2d93a699722395ae18f",
    "0xecd135fa4f61a655311e86238c92adcd779555d2",
    "0x1975bd06d486162d5dc297798dfc41edd5d160a7",
    "0xa3acf3a1e16b1d7c315e23510fdd7847b48234f6",
    "0x319f70bab6845585f412ec7724b744fec6095c85",
    "0x06706dd3f2c9abf0a21ddcc6941d9b86f0596936",
    "0x5c8536898fbb74fc7445814902fd08422eac56d0",
    "0x6966ab0d485353095148a2155858910e0965b6f9",
    "0x779543a0491a837ca36ce8c635d6154e3c4911a6",
    "0x2a5ed960395e2a49b1c758cef4aa15213cfd874c",
    "0x5c6e67ccd5849c0d29219c4f95f1a7a93b3f5dc5",
    "0x9c50426be05db97f5d64fc54bf89eff947f0a321",
    "0x200450f06520bdd6c527622a273333384d870efb",
    "0xbe8539bfe837b67d1282b2b1d61c3f723966f049",
    "0x6b0c4d41ba9ab8d8cfb5d379c69a612f2ced8ecb",
    "0xf1385fb24aad0cd7432824085e42aff90886fef5",
    "0xd1ac8b1ef1b69ff51d1d401a476e7e612414f091",
    "0x8163e7fb499e90f8544ea62bbf80d21cd26d9efd",
    "0x51e0ddd9998364a2eb38588679f0d2c42653e4a6",
    "0x627a0a960c079c21c34f7612d5d230e01b4ad4c7",
    "0xf0b1aa0eb660754448a7937c022e30aa692fe0c5",
    "0x24c4d950dfd4dd1902bbed3508144a54542bba94",
    "0x9f27daea7aca0aa0446220b98d028715e3bc803d",
    "0xa5dc5acd6a7968a4554d89d65e59b7fd3bff0f90",
    "0xd9aef3a1e38a39c16b31d1ace71bca8ef58d315b",
    "0x63ed5a272de2f6d968408b4acb9024f4cc208ebf",
    "0x6f6704e5a10332af6672e50b3d9754dc460dfa4d",
    "0x77ca7b50b6cd7e2f3fa008e24ab793fd56cb15f6",
    "0x492ea3bb0f3315521c31f273e565b868fc090f17",
    "0x0ff30d6de14a8224aa97b78aea5388d1c51c1f00",
    "0x9ea779f907f0b315b364b0cfc39a0fde5b02a416",
    "0xceaeb481747ca6c540a000c1f3641f8cef161fa7",
    "0xcc34673c6c40e791051898567a1222daf90be287",
    "0x579a80d909f346fbfb1189493f521d7f48d52238",
    "0xe308bd1ac5fda103967359b2712dd89deffb7973",
    "0x4cb31628079fb14e4bc3cd5e30c2f7489b00960c",
    "0xac1ecab32727358dba8962a0f3b261731aad9723",
    "0x4fd6ace747f06ece9c49699c7cabc62d02211f75",
    "0x440c59b325d2997a134c2c7c60a8c61611212bad",
    "0x4486a3d68fac6967006d7a517b889fd3f98c102b",
    "0x9c15b54878ba618f494b38f0ae7443db6af648ba",
    "0x27b137a85656544b1ccb5a0f2e561a5703c6a68f",
    "0x21c7fdb9ed8d291d79ffd82eb2c4356ec0d81241",
    "0x23b75c2f6791eef49c69684db4c6c1f93bf49a50",
    "0x1ca6abd14d30affe533b24d7a21bff4c2d5e1f3b",
    "0xb9637156d330c0d605a791f1c31ba5890582fe1c",
    "0x6131c42fa982e56929107413a9d526fd99405560",
    "0x1591fc0f688c81fbeb17f5426a162a7024d430c2",
    "0x542a9515200d14b68e934e9830d91645a980dd7a",
    "0xc4bbd073882dd2add2424cf47d35213405b01324",
    "0x782495b7b3355efb2833d56ecb34dc22ad7dfcc4",
    "0x58b95c9a9d5d26825e70a82b6adb139d3fd829eb",
    "0x3ba4d81db016dc2890c81f3acec2454bff5aada5",
    "0xb52042c8ca3f8aa246fa79c3feaa3d959347c0ab",
    "0xe4ae1efdfc53b73893af49113d8694a057b9c0d1",
    "0x3c02a7bc0391e86d91b7d144e61c2c01a25a79c5",
    "0x0737a6b837f97f46ebade41b9bc3e1c509c85c53",
    "0x97f43a37f595ab5dd318fb46e7a155eae057317a",
    "0x52c5317c848ba20c7504cb2c8052abd1fde29d03",
    "0x4863226780fe7c0356454236d3b1c8792785748d",
    "0x5d2b2e6fcbe3b11d26b525e085ff818dae332479",
    "0x5f9f3392e9f62f63b8eac0beb55541fc8627f42c",
    "0x057b56736d32b86616a10f619859c6cd6f59092a",
    "0x9aa008f65de0b923a2a4f02012ad034a5e2e2192",
    "0x304a554a310c7e546dfe434669c62820b7d83490",
    "0x914d1b8b43e92723e64fd0a06f5bdb8dd9b10c79",
    "0x4deb0033bb26bc534b197e61d19e0733e5679784",
    "0x07f5c1e1bc2c93e0402f23341973a0e043f7bf8a",
    "0x35a051a0010aba705c9008d7a7eff6fb88f6ea7b",
    "0x4fa802324e929786dbda3b8820dc7834e9134a2a",
    "0x9da397b9e80755301a3b32173283a91c0ef6c87e",
    "0x8d9edb3054ce5c5774a420ac37ebae0ac02343c6",
    "0x0101f3be8ebb4bbd39a2e3b9a3639d4259832fd9",
    "0x5dc28b15dffed94048d73806ce4b7a4612a1d48f",
    "0xbcf899e6c7d9d5a215ab1e3444c86806fa854c76",
    "0x12e626b0eebfe86a56d633b9864e389b45dcb260",
    "0xa2f1ccba9395d7fcb155bba8bc92db9bafaeade7",
    "0xec8e57756626fdc07c63ad2eafbd28d08e7b0ca5",
    "0xd164b088bd9108b60d0ca3751da4bceb207b0782",
    "0x6231b6d0d5e77fe001c2a460bd9584fee60d409b",
    "0x1cba23d343a983e9b5cfd19496b9a9701ada385f",
    "0xa82f360a8d3455c5c41366975bde739c37bfeb8a",
    "0x9fcd2deaff372a39cc679d5c5e4de7bafb0b1339",
    "0x005f5cee7a43331d5a3d3eec71305925a62f34b6",
    "0x0e0da70933f4c7849fc0d203f5d1d43b9ae4532d",
    "0xd131637d5275fd1a68a3200f4ad25c71a2a9522e",
    "0xbc07118b9ac290e4622f5e77a0853539789effbe",
    "0x47e7aa56d6bdf3f36be34619660de61275420af8",
    "0xacd87e28b0c9d1254e868b81cba4cc20d9a32225",
    "0xadf80daec7ba8dcf15392f1ac611fff65d94f880",
    "0x5524c55fb03cf21f549444ccbecb664d0acad706",
    "0x40b803a9abce16f50f36a77ba41180eb90023925",
    "0xfe24cdd8648121a43a7c86d289be4dd2951ed49f",
    "0x17802f43a0137c506ba92291391a8a8f207f487d",
    "0x253488078a4edf4d6f42f113d1e62836a942cf1a",
    "0x86af3e9626fce1957c82e88cbf04ddf3a2ed7915",
    "0xb136707642a4ea12fb4bae820f03d2562ebff487",
    "0xdbe9b615a3ae8709af8b93336ce9b477e4ac0940",
    "0xf14c14075d6c4ed84b86798af0956deef67365b5",
    "0xca544e5c4687d109611d0f8f928b53a25af72448",
    "0xaeeb8ff27288bdabc0fa5ebb731b6f409507516c",
    "0xcbb9d3703e651b0d496cdefb8b92c25aeb2171f7",
    "0x6d87578288b6cb5549d5076a207456a1f6a63dc0",
    "0xb2c6f0dfbb716ac562e2d85d6cb2f8d5ee87603e",
    "0xaccc230e8a6e5be9160b8cdf2864dd2a001c28b6",
    "0x2b3455ec7fedf16e646268bf88846bd7a2319bb2",
    "0x4613f3bca5c44ea06337a9e439fbc6d42e501d0a",
    "0xd343b217de44030afaa275f54d31a9317c7f441e",
    "0x84ef4b2357079cd7a7c69fd7a37cd0609a679106",
    "0xda2fef9e4a3230988ff17df2165440f37e8b1708",
    "0xf4c64518ea10f995918a454158c6b61407ea345c",
    "0x7602b46df5390e432ef1c307d4f2c9ff6d65cc97",
    "0xbb9bc244d798123fde783fcc1c72d3bb8c189413",
    "0x807640a13483f8ac783c557fcdf27be11ea4ac7a",
]
