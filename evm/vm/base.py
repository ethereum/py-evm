from __future__ import absolute_import
from abc import (
    ABCMeta,
    abstractmethod
)
import contextlib
import functools
import logging
from typing import List  # noqa: F401

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
from evm.exceptions import (
    BlockNotFound,
    ValidationError,
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


class BaseVM(Configurable, metaclass=ABCMeta):
    """
    The VM class represents the Chain rules for a specific protocol definition
    such as the Frontier or Homestead network.  Define a Chain which specifies
    the individual VM classes for each fork of the protocol rules within that
    network.
    """
    fork = None
    chaindb = None
    _state_class = None

    def __init__(self, header, chaindb):
        self.chaindb = chaindb
        self.block = self.get_block_class().from_header(header=header, chaindb=self.chaindb)
        self.state = self.get_state_class()(
            db=self.chaindb.db,
            execution_context=self.block.header.create_execution_context(self.previous_hashes),
            state_root=self.block.header.state_root,
            gas_used=self.block.header.gas_used,
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

    @abstractmethod
    def make_receipt(self, transaction, computation, state):
        """
        Make receipt.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_transaction(self, transaction):
        """
        Apply the transaction to the vm in the current block.
        """
        state_root, computation = self.state.apply_transaction(transaction)
        receipt = self.make_receipt(transaction, computation, self.state)
        # TODO: remove this mutation.
        self.state.gas_used = receipt.gas_used

        new_header = self.block.header.copy(
            bloom=int(BloomFilter(self.block.header.bloom) | receipt.bloom),
            gas_used=receipt.gas_used,
            state_root=state_root,
        )
        self.block = self.block.copy(
            header=new_header,
            transactions=tuple(self.block.transactions) + (transaction,),
        )

        return self.block, receipt, computation

    #
    # Mining
    #
    def import_block(self, block):
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
            gas_used=self.block.header.gas_used,
        )

        # run all of the transactions.
        execution_data = [
            self.apply_transaction(transaction)
            for transaction
            in block.transactions
        ]
        if execution_data:
            _, receipts, _ = zip(*execution_data)
        else:
            receipts = tuple()

        tx_root_hash, tx_kv_nodes = make_trie_root_and_nodes(block.transactions)
        receipt_root_hash, receipt_kv_nodes = make_trie_root_and_nodes(receipts)

        self.chaindb.persist_trie_data_dict(tx_kv_nodes)
        self.chaindb.persist_trie_data_dict(receipt_kv_nodes)

        self.block = self.block.copy(
            header=self.block.header.copy(
                transaction_root=tx_root_hash,
                receipt_root=receipt_root_hash,
            ),
        )

        return self.mine_block()

    def mine_block(self, *args, **kwargs):
        """
        Mine the current block. Proxies to self.pack_block method.
        """
        block = self.pack_block(self.block, *args, **kwargs)

        if block.number == 0:
            return block
        else:
            return self.state.finalize_block(block)

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

        # Perform validation
        self.validate_block(packed_block)

        return packed_block

    @contextlib.contextmanager
    def state_in_temp_block(self):
        header = self.block.header
        temp_block = self.generate_block_from_parent_header_and_coinbase(header, header.coinbase)
        prev_hashes = (header.hash, ) + self.previous_hashes

        state = self.get_state_class()(
            db=self.chaindb.db,
            execution_context=temp_block.header.create_execution_context(prev_hashes),
            state_root=temp_block.header.state_root,
            gas_used=0,
        )

        snapshot = state.snapshot()
        yield state
        state.revert(snapshot)

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

    #
    # Validate
    #
    def validate_block(self, block):
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
        if uncle.block_number >= block.number:
            raise ValidationError(
                "Uncle number ({0}) is higher than block number ({1})".format(
                    uncle.block_number, block.number))
        try:
            parent_header = get_block_header_by_hash(uncle.parent_hash, self.chaindb)
        except BlockNotFound:
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
    # Transactions
    #

    @classmethod
    def get_transaction_class(cls):
        """
        Return the class that this VM uses for transactions.
        """
        return cls.get_block_class().get_transaction_class()

    def create_transaction(self, *args, **kwargs):
        """
        Proxy for instantiating a transaction for this VM.
        """
        return self.get_transaction_class()(*args, **kwargs)

    def create_unsigned_transaction(self, *args, **kwargs):
        """
        Proxy for instantiating a transaction for this VM.
        """
        return self.get_transaction_class().create_unsigned_transaction(*args, **kwargs)

    #
    # Blocks
    #
    @classmethod
    def get_block_class(cls):
        """
        Return the class that the state class uses for blocks.
        """
        return cls.get_state_class().get_block_class()

    @classmethod
    def get_block_by_header(cls, block_header, db):
        return cls.get_block_class().from_header(block_header, db)

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
            except (IndexError, BlockNotFound):
                break

    @property
    def previous_hashes(self):
        return self.get_prev_hashes(self.block.header.parent_hash, self.chaindb)

    #
    # Headers
    #
    @classmethod
    @abstractmethod
    def create_header_from_parent(cls, parent_header, **header_params):
        """
        Creates and initializes a new block header from the provided
        `parent_header`.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def configure_header(self, **header_params):
        """
        Setup the current header with the provided parameters.  This can be
        used to set fields like the gas limit or timestamp to value different
        than their computed defaults.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    @abstractmethod
    def compute_difficulty(cls, parent_header, timestamp):
        raise NotImplementedError("Must be implemented by subclasses")

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
