from evm.rlp.headers import BlockHeader

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evm.db.chain import BaseChainDB  # noqa: F401


def make_block_number_to_hash_lookup_key(block_number: int) -> bytes:
    number_to_hash_key = b'block-number-to-hash:%d' % block_number
    return number_to_hash_key


def make_block_hash_to_score_lookup_key(block_hash: bytes) -> bytes:
    return b'block-hash-to-score:%s' % block_hash


def make_transaction_hash_to_data_lookup_key(transaction_hash: bytes) -> bytes:
    '''
    Look up a transaction that is pending, after being issued locally
    '''
    return b'transaction-hash-to-data:%s' % transaction_hash


def make_transaction_hash_to_block_lookup_key(transaction_hash: bytes) -> bytes:
    return b'transaction-hash-to-block:%s' % transaction_hash


def get_parent_header(block_header: BlockHeader, db: 'BaseChainDB') -> BlockHeader:
    """
    Returns the header for the parent block.
    """
    return db.get_block_header_by_hash(block_header.parent_hash)


def get_block_header_by_hash(block_hash: BlockHeader, db: 'BaseChainDB') -> BlockHeader:
    """
    Returns the header for the parent block.
    """
    return db.get_block_header_by_hash(block_hash)
