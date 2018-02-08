from evm.db.chain import (
    BaseChainDB,
)

from trinity.utils.ipc import (
    ObjectOverIPC,
    IPCMethod,
)


class PipeChainDB(ObjectOverIPC, BaseChainDB):
    #
    # Canonical chain API
    #
    get_canonical_head = IPCMethod('get_canonical_head')
    get_canonical_block_header_by_number = IPCMethod('get_canonical_block_header_by_number')

    #
    # Block Header API
    #
    get_block_header_by_hash = IPCMethod('get_block_header_by_hash')
    header_exists = IPCMethod('header_exists')
    persist_header_to_db = IPCMethod('persist_header_to_db')

    #
    # Block API
    lookup_block_hash = IPCMethod('lookup_block_hash')
    get_block_uncles = IPCMethod('get_block_uncles')
    get_score = IPCMethod('get_score')
    persist_block_to_db = IPCMethod('persist_block_to_db')

    #
    # Transaction and Receipt API
    #
    get_receipts = IPCMethod('get_receipts')
    get_block_transaction_hashes = IPCMethod('get_block_transaction_hashes')
    get_block_transactions = IPCMethod('get_block_transactions')
    get_transaction_by_index = IPCMethod('get_transaction_by_index')
    get_pending_transaction = IPCMethod('get_pending_transaction')
    get_transaction_index = IPCMethod('get_transaction_index')
    add_pending_transaction = IPCMethod('add_pending_transaction')
    add_transaction = IPCMethod('add_transaction')
    add_receipt = IPCMethod('add_receipt')

    #
    # Raw Database API
    #
    exists = IPCMethod('exists')
    persist_trie_data_dict_to_db = IPCMethod('persist_trie_data_dict_to_db')

    #
    # Snapshot and revert API
    #
    snapshot = IPCMethod('snapshot')
    revert = IPCMethod('revert')
    commit = IPCMethod('commit')
    clear = IPCMethod('clear')

    #
    # State Database API
    #
    get_state_db = IPCMethod('get_state_db')
