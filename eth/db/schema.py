from eth_typing import (
    BlockNumber,
    Hash32,
)

from eth.abc import (
    SchemaAPI,
)


class SchemaV1(SchemaAPI):
    @staticmethod
    def make_canonical_head_hash_lookup_key() -> bytes:
        return b"v1:canonical_head_hash"

    @staticmethod
    def make_block_number_to_hash_lookup_key(block_number: BlockNumber) -> bytes:
        number_to_hash_key = f"block-number-to-hash:{block_number}".encode()
        return number_to_hash_key

    @staticmethod
    def make_block_hash_to_score_lookup_key(block_hash: Hash32) -> bytes:
        return f"block-hash-to-score:{block_hash}".encode()

    @staticmethod
    def make_header_chain_gaps_lookup_key() -> bytes:
        return b"v1:header_chain_gaps"

    @staticmethod
    def make_chain_gaps_lookup_key() -> bytes:
        return b"v1:chain_gaps"

    @staticmethod
    def make_checkpoint_headers_key() -> bytes:
        """
        Checkpoint header hashes stored as concatenated 32 byte values
        """
        return b"v1:checkpoint-header-hashes-list"

    @staticmethod
    def make_transaction_hash_to_block_lookup_key(transaction_hash: Hash32) -> bytes:
        return f"transaction-hash-to-block:{transaction_hash}".encode()

    @staticmethod
    def make_withdrawal_hash_to_block_lookup_key(withdrawal_hash: Hash32) -> bytes:
        return f"withdrawal-hash-to-block:{withdrawal_hash}".encode()
