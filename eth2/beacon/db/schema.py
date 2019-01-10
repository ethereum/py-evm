from abc import ABC, abstractmethod

from eth_typing import (
    Hash32,
)


class BaseSchema(ABC):
    #
    # Block
    #
    @staticmethod
    @abstractmethod
    def make_canonical_head_root_lookup_key() -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def make_block_slot_to_root_lookup_key(slot: int) -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def make_block_root_to_score_lookup_key(block_root: Hash32) -> bytes:
        pass


class SchemaV1(BaseSchema):
    #
    # Block
    #
    @staticmethod
    def make_canonical_head_root_lookup_key() -> bytes:
        return b'v1:beacon:canonical-head-root'

    @staticmethod
    def make_block_slot_to_root_lookup_key(slot: int) -> bytes:
        slot_to_root_key = b'v1:beacon:block-slot-to-root:%d' % slot
        return slot_to_root_key

    @staticmethod
    def make_block_root_to_score_lookup_key(block_root: Hash32) -> bytes:
        return b'v1:beacon:block-root-to-score:%s' % block_root
