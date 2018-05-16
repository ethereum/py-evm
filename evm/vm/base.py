from __future__ import absolute_import
from abc import (
    ABCMeta,
    abstractmethod
)
import contextlib
import functools
import logging
from typing import (  # noqa: F401
    List,
    Type,
)

import rlp

from eth_bloom import (
    BloomFilter,
)

from eth_utils import (
    to_tuple,
)

from eth_hash.auto import keccak

from evm.constants import (
    GENESIS_PARENT_HASH,
    MAX_PREV_HEADER_DEPTH,
    MAX_UNCLES,
)
from evm.db.trie import make_trie_root_and_nodes
from evm.db.chain import BaseChainDB  # noqa: F401
from evm.exceptions import (
    HeaderNotFound,
    ValidationError,
)
from evm.rlp.blocks import (  # noqa: F401
    BaseBlock,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.rlp.receipts import Receipt  # noqa: F401
from evm.utils.datatypes import (
    Configurable,
)
from evm.utils.db import (
    get_parent_header,
    get_block_header_by_hash,
)
from evm.utils.headers import (
    generate_header_from_parent_header,
)
from evm.validation import (
    validate_length_lte,
    validate_gas_limit,
)
from evm.vm.message import (
    Message,
)
from evm.vm.state import BaseState  # noqa: F401


class BaseVM(Configurable, metaclass=ABCMeta):
    block = None  # type: BaseBlock
    block_class = None  # type: Type[BaseBlock]
    fork = None  # type: str
    chaindb = None  # type: BaseChainDB
    _state_class = None  # type: Type[BaseState]

    @abstractmethod
    def __init__(self, header, chaindb):
        pass

    #
    # Logging
    #
    @property
    @abstractmethod
    def logger(self):
        raise NotImplementedError("VM classes must implement this method")

    #
    # Execution
    #
    @abstractmethod
    def apply_transaction(self, header, transaction):
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def execute_bytecode(self,
                         origin,
                         gas_price,
                         gas,
                         to,
                         sender,
                         value,
                         data,
                         code,
                         code_address=None):
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def make_receipt(self, base_header, transaction, computation, state):
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
    def import_block(self, block):
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def mine_block(self, *args, **kwargs):
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def set_block_transactions(self, base_block, new_header, transactions, receipts):
        raise NotImplementedError("VM classes must implement this method")

    #
    # Finalization
    #
    @abstractmethod
    def finalize_block(self, block):
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def pack_block(self, block, *args, **kwargs):
        raise NotImplementedError("VM classes must implement this method")

    #
    # Headers
    #
    @classmethod
    @abstractmethod
    def compute_difficulty(cls, parent_header, timestamp):
        """
        Compute the difficulty for a block header.

        :param parent_header: the parent header
        :param timestamp: the timestamp of the child header
        """
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def configure_header(self, **header_params):
        """
        Setup the current header with the provided parameters.  This can be
        used to set fields like the gas limit or timestamp to value different
        than their computed defaults.
        """
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def create_header_from_parent(cls, parent_header, **header_params):
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
    def generate_block_from_parent_header_and_coinbase(cls, parent_header, coinbase):
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def get_block_class(cls) -> Type['BaseBlock']:
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
    def get_prev_hashes(cls, last_block_hash, db):
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
    def create_transaction(self, *args, **kwargs):
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def create_unsigned_transaction(self, *args, **kwargs):
        raise NotImplementedError("VM classes must implement this method")

    @classmethod
    @abstractmethod
    def get_transaction_class(cls):
        raise NotImplementedError("VM classes must implement this method")

    #
    # Validate
    #
    @abstractmethod
    def validate_block(self, block):
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def validate_transaction_against_header(self, base_header, transaction):
        """
        Validate that the given transaction is valid to apply to the given header.

        :param base_header: header before applying the transaction
        :param transaction: the transaction to validate

        :raises: ValidationError if the transaction is not valid to apply
        """
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    def validate_uncle(self, block, uncle):
        raise NotImplementedError("VM classes must implement this method")

    #
    # State
    #
    @classmethod
    @abstractmethod
    def get_state_class(cls):
        raise NotImplementedError("VM classes must implement this method")

    @abstractmethod
    @contextlib.contextmanager
    def state_in_temp_block(self):
        raise NotImplementedError("VM classes must implement this method")


class VM(BaseVM):
    """
    The :class:`~evm.vm.base.BaseVM` class represents the Chain rules for a
    specific protocol definition such as the Frontier or Homestead network.

      .. note::

        Each :class:`~evm.vm.base.BaseVM` class must be configured with:

        - ``block_class``: The :class:`~evm.rlp.blocks.Block` class for blocks in this VM ruleset.
        - ``_state_class``: The :class:`~evm.vm.state.State` class used by this VM for execution.
    """
    def __init__(self, header, chaindb):
        self.chaindb = chaindb
        self.block = self.get_block_class().from_header(header=header, chaindb=self.chaindb)
        self.state = self.get_state_class()(
            db=self.chaindb.db,
            execution_context=self.block.header.create_execution_context(self.previous_hashes),
            state_root=self.block.header.state_root,
        )

    #
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('evm.vm.base.VM.{0}'.format(self.__class__.__name__))

    #
    # Execution
    #
    def apply_transaction(self, header, transaction):
        """
        Apply the transaction to the current block. This is a wrapper around
        :func:`~evm.vm.state.State.apply_transaction` with some extra orchestration logic.

        :param header: header of the block before application
        :param transaction: to apply
        """
        self.validate_transaction_against_header(header, transaction)
        state_root, computation = self.state.apply_transaction(transaction)
        receipt = self.make_receipt(header, transaction, computation, self.state)

        new_header = header.copy(
            bloom=int(BloomFilter(header.bloom) | receipt.bloom),
            gas_used=receipt.gas_used,
            state_root=state_root,
        )

        return new_header, receipt, computation

    def execute_bytecode(self,
                         origin,
                         gas_price,
                         gas,
                         to,
                         sender,
                         value,
                         data,
                         code,
                         code_address=None,
                         ):
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

    def _apply_all_transactions(self, transactions, base_header):
        receipts = []
        previous_header = base_header
        result_header = base_header

        for transaction in transactions:
            result_header, receipt, _ = self.apply_transaction(previous_header, transaction)

            previous_header = result_header
            receipts.append(receipt)

        return result_header, receipts

    #
    # Mining
    #
    def import_block(self, block):
        """
        Import the given block to the chain.
        """
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
        self.state = self.get_state_class()(
            db=self.chaindb.db,
            execution_context=self.block.header.create_execution_context(self.previous_hashes),
            state_root=self.block.header.state_root,
        )

        # run all of the transactions.
        last_header, receipts = self._apply_all_transactions(block.transactions, self.block.header)

        self.block = self.set_block_transactions(
            self.block,
            last_header,
            block.transactions,
            receipts,
        )

        return self.mine_block()

    def mine_block(self, *args, **kwargs):
        """
        Mine the current block. Proxies to self.pack_block method.
        """
        packed_block = self.pack_block(self.block, *args, **kwargs)

        if packed_block.number == 0:
            final_block = packed_block
        else:
            final_block = self.finalize_block(packed_block)

        # Perform validation
        self.validate_block(final_block)

        return final_block

    def set_block_transactions(self, base_block, new_header, transactions, receipts):

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
    def finalize_block(self, block):
        """
        Perform any finalization steps like awarding the block mining reward.
        """
        block_reward = self.get_block_reward() + (
            len(block.uncles) * self.get_nephew_reward()
        )

        self.state.account_db.delta_balance(block.header.coinbase, block_reward)
        self.logger.debug(
            "BLOCK REWARD: %s -> %s",
            block_reward,
            block.header.coinbase,
        )

        for uncle in block.uncles:
            uncle_reward = self.get_uncle_reward(block.number, uncle)
            self.state.account_db.delta_balance(uncle.coinbase, uncle_reward)
            self.logger.debug(
                "UNCLE REWARD REWARD: %s -> %s",
                uncle_reward,
                uncle.coinbase,
            )
        # We need to call `persist` here since the state db batches
        # all writes until we tell it to write to the underlying db
        # TODO: Refactor to only use batching/journaling for tx processing
        self.state.account_db.persist()

        return block.copy(header=block.header.copy(state_root=self.state.state_root))

    def pack_block(self, block, *args, **kwargs):
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
            kwargs.setdefault('uncles_hash', keccak(rlp.encode(block.uncles)))
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
    def generate_block_from_parent_header_and_coinbase(cls, parent_header, coinbase):
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
    def get_block_class(cls) -> Type['BaseBlock']:
        """
        Return the :class:`~evm.rlp.blocks.Block` class that this VM uses for blocks.
        """
        if cls.block_class is None:
            raise AttributeError("No `block_class` has been set for this VM")
        else:
            return cls.block_class

    @classmethod
    @functools.lru_cache(maxsize=32)
    @to_tuple
    def get_prev_hashes(cls, last_block_hash, db):
        if last_block_hash == GENESIS_PARENT_HASH:
            return

        block_header = get_block_header_by_hash(last_block_hash, db)

        for _ in range(MAX_PREV_HEADER_DEPTH):
            yield block_header.hash
            try:
                block_header = get_parent_header(block_header, db)
            except (IndexError, HeaderNotFound):
                break

    @property
    def previous_hashes(self):
        """
        Convenience API for accessing the previous 255 block hashes.
        """
        return self.get_prev_hashes(self.block.header.parent_hash, self.chaindb)

    #
    # Transactions
    #
    def create_transaction(self, *args, **kwargs):
        """
        Proxy for instantiating a signed transaction for this VM.
        """
        return self.get_transaction_class()(*args, **kwargs)

    def create_unsigned_transaction(self, *args, **kwargs):
        """
        Proxy for instantiating an unsigned transaction for this VM.
        """
        return self.get_transaction_class().create_unsigned_transaction(*args, **kwargs)

    @classmethod
    def get_transaction_class(cls):
        """
        Return the class that this VM uses for transactions.
        """
        return cls.get_block_class().get_transaction_class()

    #
    # Validate
    #
    def validate_block(self, block):
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
        if not block.is_genesis:
            parent_header = get_parent_header(block.header, self.chaindb)

            validate_gas_limit(block.header.gas_limit, parent_header.gas_limit)
            validate_length_lte(block.header.extra_data, 32, title="BlockHeader.extra_data")

            # timestamp
            if block.header.timestamp < parent_header.timestamp:
                raise ValidationError(
                    "`timestamp` is before the parent block's timestamp.\n"
                    "- block  : {0}\n"
                    "- parent : {1}. ".format(
                        block.header.timestamp,
                        parent_header.timestamp,
                    )
                )
            elif block.header.timestamp == parent_header.timestamp:
                raise ValidationError(
                    "`timestamp` is equal to the parent block's timestamp\n"
                    "- block : {0}\n"
                    "- parent: {1}. ".format(
                        block.header.timestamp,
                        parent_header.timestamp,
                    )
                )

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

        for uncle in block.uncles:
            self.validate_uncle(block, uncle)

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
                    block.header.uncle_hash,
                )
            )

    def validate_uncle(self, block, uncle):
        """
        Validate the given uncle in the context of the given block.
        """
        if uncle.block_number >= block.number:
            raise ValidationError(
                "Uncle number ({0}) is higher than block number ({1})".format(
                    uncle.block_number, block.number))
        try:
            parent_header = get_block_header_by_hash(uncle.parent_hash, self.chaindb)
        except HeaderNotFound:
            raise ValidationError(
                "Uncle ancestor not found: {0}".format(uncle.parent_hash))
        if uncle.block_number != parent_header.block_number + 1:
            raise ValidationError(
                "Uncle number ({0}) is not one above ancestor's number ({1})".format(
                    uncle.block_number, parent_header.block_number))
        if uncle.timestamp < parent_header.timestamp:
            raise ValidationError(
                "Uncle timestamp ({0}) is before ancestor's timestamp ({1})".format(
                    uncle.timestamp, parent_header.timestamp))
        if uncle.gas_used > uncle.gas_limit:
            raise ValidationError(
                "Uncle's gas usage ({0}) is above the limit ({1})".format(
                    uncle.gas_used, uncle.gas_limit))

    #
    # State
    #
    @classmethod
    def get_state_class(cls):
        """
        Return the class that this VM uses for states.
        """
        if cls._state_class is None:
            raise AttributeError("No `_state_class` has been set for this VM")

        return cls._state_class

    @contextlib.contextmanager
    def state_in_temp_block(self):
        header = self.block.header
        temp_block = self.generate_block_from_parent_header_and_coinbase(header, header.coinbase)
        prev_hashes = (header.hash, ) + self.previous_hashes

        state = self.get_state_class()(
            db=self.chaindb.db,
            execution_context=temp_block.header.create_execution_context(prev_hashes),
            state_root=temp_block.header.state_root,
        )

        snapshot = state.snapshot()
        yield state
        state.revert(snapshot)
