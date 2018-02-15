from trie import (
    BinaryTrie,
    HexaryTrie,
)

from evm.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)


def make_block_number_to_hash_lookup_key(block_number):
    number_to_hash_key = b'block-number-to-hash:%d' % block_number
    return number_to_hash_key


def make_block_hash_to_score_lookup_key(block_hash):
    return b'block-hash-to-score:%s' % block_hash


def make_transaction_hash_to_data_lookup_key(transaction_hash):
    '''
    Look up a transaction that is pending, after being issued locally
    '''
    return b'transaction-hash-to-data:%s' % transaction_hash


def make_transaction_hash_to_block_lookup_key(transaction_hash):
    return b'transaction-hash-to-block:%s' % transaction_hash


def get_parent_header(block_header, db):
    """
    Returns the header for the parent block.
    """
    return db.get_block_header_by_hash(block_header.parent_hash)


def get_block_header_by_hash(block_hash, db):
    """
    Returns the header for the parent block.
    """
    return db.get_block_header_by_hash(block_hash)


def get_empty_root_hash(db):
    root_hash = None
    if db.trie_class is HexaryTrie:
        root_hash = BLANK_ROOT_HASH
    elif db.trie_class is BinaryTrie:
        root_hash = EMPTY_SHA3
    elif db.trie_class is None:
        raise AttributeError(
            "BaseChainDB must declare a trie_class."
        )
    else:
        raise NotImplementedError(
            "db.trie_class {} is not supported.".format(db.trie_class)
        )
    return root_hash
