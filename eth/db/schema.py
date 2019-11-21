from eth_typing import (
    BlockNumber,
    Hash32,
)

from eth.abc import SchemaAPI


class SchemaV1(SchemaAPI):
    @staticmethod
    def make_canonical_head_hash_lookup_key() -> bytes:
        return b'v1:canonical_head_hash'

    @staticmethod
    def make_block_number_to_hash_lookup_key(block_number: BlockNumber) -> bytes:
        number_to_hash_key = b'block-number-to-hash:%d' % block_number
        return number_to_hash_key

    @staticmethod
    def make_block_hash_to_score_lookup_key(block_hash: Hash32) -> bytes:
        return b'block-hash-to-score:%s' % block_hash

    @staticmethod
    def make_transaction_hash_to_block_lookup_key(transaction_hash: Hash32) -> bytes:
        return b'transaction-hash-to-block:%s' % transaction_hash
