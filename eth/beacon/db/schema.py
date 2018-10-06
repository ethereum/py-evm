from abc import ABC, abstractmethod

from eth_typing import (
    Hash32,
)


class BaseSchema(ABC):
    @staticmethod
    @abstractmethod
    def make_canonical_head_hash_lookup_key() -> bytes:
        raise NotImplementedError('Must be implemented by subclasses')

    @staticmethod
    @abstractmethod
    def make_block_slot_to_hash_lookup_key(slot: int) -> bytes:
        raise NotImplementedError('Must be implemented by subclasses')

    @staticmethod
    @abstractmethod
    def make_block_hash_to_score_lookup_key(block_hash: Hash32) -> bytes:
        raise NotImplementedError('Must be implemented by subclasses')


class SchemaV1(BaseSchema):
    @staticmethod
    def make_canonical_head_hash_lookup_key() -> bytes:
        return b'v1:beacon:canonical_head_hash'

    @staticmethod
    def make_block_slot_to_hash_lookup_key(slot: int) -> bytes:
        slot_to_hash_key = b'beacon:block-slot-to-hash:%d' % slot
        return slot_to_hash_key

    @staticmethod
    def make_block_hash_to_score_lookup_key(block_hash: Hash32) -> bytes:
        return b'beacon:block-hash-to-score:%s' % block_hash
