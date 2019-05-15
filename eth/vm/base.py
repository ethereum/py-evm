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
from typing import Set  # noqa: F401

from eth_hash.auto import keccak
from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
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
from eth.db.chain import BaseChainDB  # noqa: F401
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
    block = None  # type: BaseBlock
    block_class = None  # type: Type[BaseBlock]
    fork = None  # type: str
    chaindb = None  # type: BaseChainDB
    _state_class = None  # type: Type[BaseState]

    @abstractmethod
    def __init__(self, header: BlockHeader, chaindb: BaseChainDB) -> None:
        pass

    @property
    @abstractmethod
    def state(self) -> BaseState:
        pass

    @classmethod
    @abstractmethod
    def build_state(
            cls,
            db: BaseAtomicDB,
            header: BlockHeader,
            previous_hashes: Iterable[Hash32] = ()) -> BaseState:
        pass

    @property
    @abstractmethod
    def header(self) -> BlockHeader:
        pass

    @property
    @abstractmethod
    def block(self) -> BaseBlock:
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
                         code_address: Address=None) -> BaseComputation:
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
    def validate_header(
            cls, header: BlockHeader, parent_header: BlockHeader, check_seal: bool = True) -> None:
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
    def validate_uncle(
            cls, block: BaseBlock, uncle: BlockHeader, uncle_parent: BlockHeader) -> None:
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

    @property
    def header(self) -> BlockHeader:
        if self._block is None:
            return self._initial_header
        else:
            return self._block.header

    @property
    def block(self) -> BaseBlock:
        if self._block is None:
            block_class = self.get_block_class()
            self._block = block_class.from_header(header=self._initial_header, chaindb=self.chaindb)
        return self._block

    @block.setter
    def block(self, block: BaseBlock) -> None:
        self._block = block

    @property
    def state(self) -> BaseState:
        if self._state is None:
            self._state = self.build_state(self.chaindb.db, self.header, self.previous_hashes)
        return self._state

    @classmethod
    def build_state(
            cls,
            db: BaseAtomicDB,
            header: BlockHeader,
            previous_hashes: Iterable[Hash32] = ()) -> BaseState:
        """
        You probably want `VM().state` instead of this.

        Occasionally, you want to build custom state against a particular header and DB,
        even if you don't have the VM initialized. This is a convenience method to do that.
        """

        execution_context = header.create_execution_context(previous_hashes)
        return cls.get_state_class()(db, execution_context, header.state_root)

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
                         code_address: Address=None,
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
        if base_header.block_number != self.header.block_number:
            raise ValidationError(
                "This VM instance must only work on block #{}, "
                "but the target header has block #{}".format(
                    self.header.block_number,
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
        if self.block.number != block.number:
            raise ValidationError(
                "This VM can only import blocks at number #{}, the attempted block was #{}".format(
                    self.block.number,
                    block.number,
                )
            )

        self.block = self.block.copy(
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
        self._state = self.build_state(self.chaindb.db, self.header, self.previous_hashes)

        # run all of the transactions.
        new_header, receipts, _ = self.apply_all_transactions(block.transactions, self.header)

        self.block = self.set_block_transactions(
            self.block,
            new_header,
            block.transactions,
            receipts,
        )

        return self.mine_block()

    def mine_block(self, *args: Any, **kwargs: Any) -> BaseBlock:
        """
        Mine the current block. Proxies to self.pack_block method.
        """
        packed_block = self.pack_block(self.block, *args, **kwargs)

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
        self.state.persist()

        return block.copy(header=block.header.copy(state_root=self.state.state_root))

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
        return self.get_prev_hashes(self.header.parent_hash, self.chaindb)

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
        already_checked = set()  # type: Set[Hash32]

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
        header = self.header
        temp_block = self.generate_block_from_parent_header_and_coinbase(header, header.coinbase)
        prev_hashes = itertools.chain((header.hash, ), self.previous_hashes)

        state = self.build_state(self.chaindb.db, temp_block.header, prev_hashes)

        snapshot = state.snapshot()
        yield state
        state.revert(snapshot)
