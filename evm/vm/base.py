from __future__ import absolute_import

import rlp
import logging

from evm.constants import (
    GENESIS_PARENT_HASH,
    MAX_PREV_HEADER_DEPTH,
)
from evm.exceptions import (
    BlockNotFound,
)
from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB
from evm.rlp.headers import (
    BlockHeader,
)
from evm.utils.db import (
    get_parent_header,
    get_block_header_by_hash,
)
from evm.utils.keccak import (
    keccak,
)
from evm.utils.headers import (
    generate_header_from_parent_header,
)


class VM(object):
    """
    The VM class represents the Chain rules for a specific protocol definition
    such as the Frontier or Homestead network.  Defining an Chain  defining
    individual VM classes for each fork of the protocol rules within that
    network.
    """
    chaindb = None
    _block_class = None
    _state_class = None

    _is_stateless = None

    def __init__(self, header, chaindb):
        self.chaindb = chaindb
        block_class = self.get_block_class()
        self.block = block_class.from_header(header=header, chaindb=self.chaindb)

    @classmethod
    def configure(cls,
                  name=None,
                  **overrides):
        if name is None:
            name = cls.__name__

        for key in overrides:
            if not hasattr(cls, key):
                raise TypeError(
                    "The VM.configure cannot set attributes that are not "
                    "already present on the base class.  The attribute `{0}` was "
                    "not found on the base class `{1}`".format(key, cls)
                )
        return type(name, (cls,), overrides)

    #
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('evm.vm.base.VM.{0}'.format(self.__class__.__name__))

    #
    # Execution
    #
    def add_transaction(self, transaction, computation):
        """
        Add a transaction to the given block and save the block data into chaindb.
        """
        receipt = self.state.make_receipt(transaction, computation)

        transaction_idx = len(self.block.transactions)

        index_key = rlp.encode(transaction_idx, sedes=rlp.sedes.big_endian_int)

        self.block.transactions.append(transaction)

        tx_root_hash = self.chaindb.add_transaction(self.block.header, index_key, transaction)
        receipt_root_hash = self.chaindb.add_receipt(self.block.header, index_key, receipt)

        self.block.bloom_filter |= receipt.bloom

        self.block.header.transaction_root = tx_root_hash
        self.block.header.receipt_root = receipt_root_hash
        self.block.header.bloom = int(self.block.bloom_filter)
        self.block.header.gas_used = receipt.gas_used

        return self.block

    def apply_transaction(self, transaction):
        """
        Apply the transaction to the vm in the current block.
        """
        if self.is_stateless:
            computation, block, trie_data = self.get_state_class().apply_transaction(
                self.state,
                transaction,
                self.block,
                is_stateless=True,
            )
            self.block = block

            # TODO: Modify Chain.apply_transaction to update the local vm state before

            # Persist changed transaction and receipt key-values to self.chaindb.
            for key, value in trie_data.items():
                self.chaindb.db[key] = value
        else:
            computation, _, _ = self.get_state_class().apply_transaction(
                self.state,
                transaction,
                self.block,
                is_stateless=False,
            )
            self.add_transaction(transaction, computation)

        self.clear_journal()

        return computation, self.block

    #
    # Mining
    #
    @staticmethod
    def get_block_reward():
        raise NotImplementedError("Must be implemented by subclasses")

    @staticmethod
    def get_uncle_reward(block_number, uncle):
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    def get_nephew_reward(cls):
        raise NotImplementedError("Must be implemented by subclasses")

    def import_block(self, block):
        self.configure_header(
            coinbase=block.header.coinbase,
            gas_limit=block.header.gas_limit,
            timestamp=block.header.timestamp,
            extra_data=block.header.extra_data,
            mix_hash=block.header.mix_hash,
            nonce=block.header.nonce,
            uncles_hash=keccak(rlp.encode(block.uncles)),
        )

        # run all of the transactions.
        for transaction in block.transactions:
            self.apply_transaction(transaction)

        # transfer the list of uncles.
        self.block.uncles = block.uncles

        return self.mine_block()

    def mine_block(self, *args, **kwargs):
        """
        Mine the current block. Proxies to self.pack_block method.
        """
        block = self.block
        self.pack_block(block, *args, **kwargs)

        if block.number == 0:
            return block

        block_reward = self.get_block_reward() + (
            len(block.uncles) * self.get_nephew_reward()
        )

        with self.state.state_db() as state_db:
            state_db.delta_balance(block.header.coinbase, block_reward)
            self.logger.debug(
                "BLOCK REWARD: %s -> %s",
                block_reward,
                block.header.coinbase,
            )

            for uncle in block.uncles:
                uncle_reward = self.get_uncle_reward(block.number, uncle)
                state_db.delta_balance(uncle.coinbase, uncle_reward)
                self.logger.debug(
                    "UNCLE REWARD REWARD: %s -> %s",
                    uncle_reward,
                    uncle.coinbase,
                )

        return block

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
            block.uncles = kwargs.pop('uncles')
            kwargs.setdefault('uncles_hash', keccak(rlp.encode(block.uncles)))

        header = block.header
        provided_fields = set(kwargs.keys())
        known_fields = set(tuple(zip(*BlockHeader.fields))[0])
        unknown_fields = provided_fields.difference(known_fields)

        if unknown_fields:
            raise AttributeError(
                "Unable to set the field(s) {0} on the `BlockHeader` class. "
                "Received the following unexpected fields: {1}.".format(
                    ", ".join(known_fields),
                    ", ".join(unknown_fields),
                )
            )

        for key, value in kwargs.items():
            setattr(header, key, value)

        # Perform validation
        self.state.validate_block(block)

        return block

    @classmethod
    def create_block(
            cls,
            transaction_packages,
            prev_headers,
            coinbase):
        """
        Create a block with transaction witness
        """
        parent_header = prev_headers[0]

        block = cls.generate_block_from_parent_header_and_coinbase(
            parent_header,
            coinbase,
        )

        recent_trie_nodes = {}
        receipts = []
        for (transaction, transaction_witness) in transaction_packages:
            transaction_witness.update(recent_trie_nodes)
            witness_db = BaseChainDB(MemoryDB(transaction_witness))

            vm_state = cls.get_state_class()(
                chaindb=witness_db,
                block_header=block.header,
                prev_headers=prev_headers,
                receipts=receipts,
            )
            computation, result_block, _ = vm_state.apply_transaction(
                transaction=transaction,
                block=block,
                is_stateless=True,
            )

            if not computation.is_error:
                block = result_block
                receipts = computation.vm_state.receipts
                recent_trie_nodes.update(computation.vm_state.access_logs.writes)
            else:
                pass

        # Finalize
        witness_db = BaseChainDB(MemoryDB(recent_trie_nodes))
        vm_state = cls.get_state_class()(
            chaindb=witness_db,
            block_header=block.header,
            prev_headers=prev_headers,
        )
        block = cls.finalize_block(vm_state, block)

        return block

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
    def finalize_block(cls, vm_state, block):
        """
        Finalize the given block (set rewards).
        """
        block_reward = cls.get_block_reward() + (
            len(block.uncles) * cls.get_nephew_reward(cls)
        )

        with vm_state.state_db() as state_db:
            state_db.delta_balance(block.header.coinbase, block_reward)
            vm_state.logger.debug(
                "BLOCK REWARD: %s -> %s",
                block_reward,
                block.header.coinbase,
            )

            for uncle in block.uncles:
                uncle_reward = cls.get_uncle_reward(block.number, uncle)
                state_db.delta_balance(uncle.coinbase, uncle_reward)
                vm_state.logger.debug(
                    "UNCLE REWARD REWARD: %s -> %s",
                    uncle_reward,
                    uncle.coinbase,
                )
        block.state_root = vm_state.block_header.state_root

        return block

    #
    # Transactions
    #
    def get_transaction_class(self):
        """
        Return the class that this VM uses for transactions.
        """
        return self.get_block_class().get_transaction_class()

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
        Return the class that this VM uses for blocks.
        """
        if cls._block_class is None:
            raise AttributeError("No `_block_class` has been set for this VM")

        return cls._block_class

    @classmethod
    def get_block_by_header(cls, block_header, db):
        return cls.get_block_class().from_header(block_header, db)

    @classmethod
    def get_prev_headers(cls, last_block_hash, db):
        prev_headers = []

        if last_block_hash == GENESIS_PARENT_HASH:
            return prev_headers

        block_header = get_block_header_by_hash(last_block_hash, db)

        for _ in range(MAX_PREV_HEADER_DEPTH):
            prev_headers.append(block_header)
            try:
                block_header = get_parent_header(block_header, db)
            except (IndexError, BlockNotFound):
                break
        return prev_headers

    #
    # Gas Usage API
    #
    def get_cumulative_gas_used(self, block):
        """
        Note return value of this function can be cached based on
        `self.receipt_db.root_hash`
        """
        if len(block.transactions):
            return block.get_receipts(self.chaindb)[-1].gas_used
        else:
            return 0

    #
    # Headers
    #
    @classmethod
    def create_header_from_parent(cls, parent_header, **header_params):
        """
        Creates and initializes a new block header from the provided
        `parent_header`.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def configure_header(self, **header_params):
        """
        Setup the current header with the provided parameters.  This can be
        used to set fields like the gas limit or timestamp to value different
        than their computed defaults.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    def compute_difficulty(cls, parent_header, timestamp):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Snapshot and Revert
    #
    def clear_journal(self):
        """
        Cleare the journal.  This should be called at any point of VM execution
        where the statedb is being committed, such as after a transaction has
        been applied to a block.
        """
        self.chaindb.clear()

    #
    # State
    #
    @property
    def is_stateless(self):
        return self._is_stateless

    @classmethod
    def get_state_class(cls):
        """
        Return the class that this VM uses for states.
        """
        if cls._state_class is None:
            raise AttributeError("No `_state_class` has been set for this VM")

        return cls._state_class

    def get_state(self, chaindb=None, block_header=None):
        """Return state object
        """
        if chaindb is None:
            chaindb = self.chaindb
        if block_header is None:
            block_header = self.block.header

        prev_headers = self.get_prev_headers(
            last_block_hash=self.block.header.parent_hash,
            db=self.chaindb,
        )
        receipts = self.block.get_receipts(self.chaindb)
        return self.get_state_class()(
            chaindb,
            block_header,
            prev_headers,
            receipts=receipts,
        )

    @property
    def state(self):
        """Return current state property
        """
        return self.get_state(
            chaindb=self.chaindb,
            block_header=self.block.header,
        )
