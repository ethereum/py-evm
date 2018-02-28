from eth_utils import (
    keccak,
)
import rlp
from trie import (
    BinaryTrie,
)

from evm.db.backends.memory import MemoryDB
from evm.db.chain import ChainDB
from evm.db.state import (
    MainAccountStateDB,
    ShardingAccountStateDB,
)
from evm.utils.state import (
    update_witness_db,
    update_recent_trie_nodes_db,
)

from .base import (
    BaseVM,
)
from .execution_context import (
    ExecutionContext,
)


class ShardVM(BaseVM):
    #
    # Apply block
    #
    def apply_block_with_witness(self, block, witness, account_state_class=ShardingAccountStateDB):
        self.configure_header(
            coinbase=block.header.coinbase,
            gas_limit=block.header.gas_limit,
            timestamp=block.header.timestamp,
            extra_data=block.header.extra_data,
            mix_hash=block.header.mix_hash,
            nonce=block.header.nonce,
            uncles_hash=keccak(rlp.encode(block.uncles)),
        )

        recent_trie_nodes_db = dict([(keccak(value), value) for value in witness])
        receipts = []
        prev_hashes = self.previous_hashes

        execution_context = ExecutionContext.from_block_header(block.header, prev_hashes)

        # run all of the transactions.
        for transaction in block.transactions:
            witness_db = ChainDB(
                MemoryDB(recent_trie_nodes_db),
                account_state_class=account_state_class,
                trie_class=BinaryTrie,
            )

            vm_state = self.get_state_class()(
                chaindb=witness_db,
                execution_context=execution_context,
                state_root=self.block.header.state_root,
                receipts=receipts,
            )
            computation, result_block, trie_data_dict = vm_state.apply_transaction(
                transaction=transaction,
                block=self.block,
            )

            if computation.is_success:
                # block = result_block
                self.block = result_block
                receipts = computation.vm_state.receipts
                recent_trie_nodes_db = update_recent_trie_nodes_db(
                    recent_trie_nodes_db,
                    computation.vm_state.access_logs.writes
                )
                self.chaindb.persist_trie_data_dict_to_db(trie_data_dict)

            else:
                pass

        # transfer the list of uncles.
        self.block.uncles = block.uncles

        witness_db = ChainDB(
            MemoryDB(recent_trie_nodes_db),
            account_state_class=account_state_class,
            trie_class=BinaryTrie,
        )

        return self.mine_block_stateless(witness_db, receipts)

    def mine_block_stateless(self, witness_db, receipts, *args, **kwargs):
        """
        Mine the current block. Proxies to self.pack_block method.
        """
        block = self.block
        self.pack_block(block, *args, **kwargs)

        if block.number == 0:
            return block

        execution_context = ExecutionContext.from_block_header(
            block.header,
            self.previous_hashes
        )

        vm_state = self.get_state_class()(
            chaindb=witness_db,
            execution_context=execution_context,
            state_root=block.header.state_root,
            receipts=receipts,
        )
        block = vm_state.finalize_block(block)

        return block

    @classmethod
    def build_block(
            cls,
            witness_package,
            prev_hashes,
            parent_header,
            account_state_class=MainAccountStateDB):
        """
        Build a block with transaction witness
        """
        block = cls.generate_block_from_parent_header_and_coinbase(
            parent_header,
            witness_package.coinbase,
        )

        recent_trie_nodes_db = {}
        block_witness = set()
        receipts = []
        transaction_packages = witness_package.transaction_packages
        for (transaction, transaction_witness) in transaction_packages:
            witness_db = update_witness_db(
                witness=transaction_witness,
                recent_trie_nodes_db=recent_trie_nodes_db,
                account_state_class=account_state_class,
            )

            execution_context = ExecutionContext.from_block_header(block.header, prev_hashes)
            vm_state = cls.get_state_class()(
                chaindb=witness_db,
                execution_context=execution_context,
                state_root=block.header.state_root,
                receipts=receipts,
            )
            computation, result_block, _ = vm_state.apply_transaction(
                transaction=transaction,
                block=block,
            )

            if computation.is_success:
                block = result_block
                receipts = computation.vm_state.receipts
                recent_trie_nodes_db = update_recent_trie_nodes_db(
                    recent_trie_nodes_db,
                    computation.vm_state.access_logs.writes
                )
                block_witness.update(transaction_witness)
            else:
                pass

        # Finalize
        # For sharding, ignore uncles and nephews.
        witness_db = update_witness_db(
            witness=witness_package.coinbase_witness,
            recent_trie_nodes_db=recent_trie_nodes_db,
            account_state_class=account_state_class,
        )

        execution_context = ExecutionContext.from_block_header(block.header, prev_hashes)
        vm_state = cls.get_state_class()(
            chaindb=witness_db,
            execution_context=execution_context,
            state_root=block.header.state_root,
            receipts=receipts,
        )
        block = vm_state.finalize_block(block)
        block_witness.update(witness_package.coinbase_witness)
        return block, block_witness
