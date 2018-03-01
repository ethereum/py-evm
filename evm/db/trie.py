import rlp
from trie import (
    HexaryTrie,
)

from evm.db.backends.memory import MemoryDB
from evm.db.chain import ChainDB


def make_trie_root_and_nodes(transactions, trie_class=HexaryTrie, chain_db_class=ChainDB):
    chaindb = chain_db_class(MemoryDB(), trie_class=trie_class)
    db = chaindb.db
    transaction_db = trie_class(db, chaindb.empty_root_hash)

    for index, transaction in enumerate(transactions):
        index_key = rlp.encode(index, sedes=rlp.sedes.big_endian_int)
        transaction_db[index_key] = rlp.encode(transaction)

    return transaction_db.root_hash, transaction_db.db.wrapped_db.kv_store
