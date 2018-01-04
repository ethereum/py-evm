from __future__ import absolute_import

import rlp
import logging

from evm.constants import (
    BLOCK_REWARD,
    GENESIS_PARENT_HASH,
    MAX_PREV_HEADER_DEPTH,
    UNCLE_DEPTH_PENALTY_FACTOR,
)
from evm.exceptions import (
    BlockNotFound,
)
from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB
from evm.rlp.headers import (
    BlockHeader,
)
from evm.utils.keccak import (
    keccak,
)
from evm.utils.headers import (
    generate_header_from_prev_state,
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
        receipt = self.state.make_receipt(self.state, transaction, computation)

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
            computation, block, trie_data = self.state.apply_transaction(
                self.state,
                transaction,
                self.block,
                is_stateless=True,
                witness_db=self.chaindb,
            )
            self.block = block

            # Persist changed transaction and receipt key-values to self.chaindb.
            for key, value in trie_data.items():
                self.chaindb.db[key] = value
        else:
            computation, _, _ = self.state.apply_transaction(
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
    @classmethod
    def get_block_reward(cls, block_number):
        return BLOCK_REWARD

    @classmethod
    def get_nephew_reward(cls, block_number):
        return cls.get_block_reward(block_number) // 32

    @classmethod
    def get_uncle_reward(cls, block_number, uncle):
        return BLOCK_REWARD * (
            UNCLE_DEPTH_PENALTY_FACTOR + uncle.block_number - block_number
        ) // UNCLE_DEPTH_PENALTY_FACTOR

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
        Mine the current block. Proxies to the current block's mine method.
        See example with FrontierBlock. :meth:`~evm.vm.forks.frontier.blocks.FrontierBlock.mine`
        """
        block = self.block
        self.pack_block(block, *args, **kwargs)

        if block.number == 0:
            return block

        block_reward = self.get_block_reward(block.number) + (
            len(block.uncles) * self.get_nephew_reward(block.number)
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
    def finalize_block(cls, vm_state, block):
        """
        Finalize the given block (set rewards).
        """
        block_reward = cls.get_block_reward(block.number) + (
            len(block.uncles) * cls.get_nephew_reward(block.number)
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

        return block, vm_state

    @classmethod
    def create_block(
            cls,
            transaction_packages,
            prev_state_root,
            parent_header,
            prev_headers,
            coinbase):
        """
        Create a block with transaction witness
        """
        # Generate block header object
        block_header = generate_header_from_prev_state(
            cls.compute_difficulty,
            prev_state_root,
            parent_header,
            parent_header.timestamp + 1,
            coinbase,
        )

        block = cls.get_block_class()(
            block_header,
            transactions=[],
            uncles=[],
        )
        vm_state = cls.get_state_class()(
            chaindb=BaseChainDB({}),
            block_header=block_header,
            prev_headers=prev_headers,
        )

        witness = {}
        witness_db = BaseChainDB(MemoryDB(witness))

        for index, (transaction, transaction_witness) in enumerate(transaction_packages):
            witness.update(transaction_witness)
            witness_db = BaseChainDB(MemoryDB(witness))
            vm_state.set_chaindb(witness_db)

            computation, block, _ = vm_state.apply_transaction(
                vm_state,
                transaction,
                block=block,
                is_stateless=True,
                witness_db=witness_db
            )
            # Update witness_db
            vm_state = computation.vm_state
            witness.update(computation.vm_state.access_logs.writes)
            witness_db = BaseChainDB(MemoryDB(witness))
            vm_state.set_chaindb(witness_db)

        block, vm_state = cls.finalize_block(vm_state, block)

        return block, vm_state.access_logs, vm_state

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

    def validate_transaction(self, transaction):
        """
        Perform chain-aware validation checks on the transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")

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

    def get_block_by_header(self, block_header, db):
        return self.get_block_class().from_header(block_header, db)

    @staticmethod
    def get_parent_header(block_header, db):
        """
        Returns the header for the parent block.
        """
        return db.get_block_header_by_hash(block_header.parent_hash)

    @staticmethod
    def get_block_header_by_hash(block_hash, db):
        """
        Returns the header for the parent block.
        """
        return db.get_block_header_by_hash(block_hash)

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

    def get_state(self, chaindb=None, block_header=None, prev_headers=None):
        """Return state object
        """
        if chaindb is None:
            chaindb = self.chaindb
        if block_header is None:  # TODO: remove
            block_header = self.block.header
        if prev_headers is None:
            prev_headers = self.get_prev_headers(
                last_block_hash=self.block.header.parent_hash,
                db=self.chaindb,
            )
        return self.get_state_class()(
            chaindb,
            block_header,  # TODO: remove
            prev_headers,
        )

    def get_prev_headers(self, last_block_hash, db):
        prev_headers = []
        if last_block_hash == GENESIS_PARENT_HASH:
            return prev_headers

        last_block_header = self.get_block_header_by_hash(last_block_hash, db)
        block = self.get_block_by_header(last_block_header, db)

        for depth in range(MAX_PREV_HEADER_DEPTH):
            prev_headers.append(block.header)
            try:
                prev_block_header = self.get_parent_header(block.header, db)
                block = self.get_block_by_header(prev_block_header, db)
            except (IndexError, BlockNotFound) as error:
                break
        return prev_headers

    @property
    def state(self):
        """Return current state property
        """
        return self.get_state(
            chaindb=self.chaindb,
            block_header=self.block.header,
        )
