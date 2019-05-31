from abc import ABC, abstractmethod

from eth_typing import (
    Hash32,
)


class BaseSchema(ABC):
    #
    # State
    #
    @staticmethod
    @abstractmethod
    def make_head_state_slot_lookup_key() -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def make_slot_to_state_root_lookup_key(slot: int) -> bytes:
        pass

    #
    # Block
    #
    @staticmethod
    @abstractmethod
    def make_canonical_head_root_lookup_key() -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def make_block_root_to_slot_lookup_key(block_root: Hash32) -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def make_block_slot_to_root_lookup_key(slot: int) -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def make_block_root_to_score_lookup_key(block_root: Hash32) -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def make_finalized_head_root_lookup_key() -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def make_justified_head_root_lookup_key() -> bytes:
        pass

    #
    # Attestaion
    #
    @staticmethod
    @abstractmethod
    def make_attestation_root_to_block_lookup_key(attestaton_root: Hash32) -> bytes:
        pass


class SchemaV1(BaseSchema):
    #
    # State
    #
    @staticmethod
    def make_head_state_slot_lookup_key() -> bytes:
        return b'v1:beacon:head-state-slot'

    @staticmethod
    def make_slot_to_state_root_lookup_key(slot: int) -> bytes:
        return b'v1:beacon:slot-to-state-root%d' % slot

    #
    # Block
    #
    @staticmethod
    def make_canonical_head_root_lookup_key() -> bytes:
        return b'v1:beacon:canonical-head-root'

    @staticmethod
    def make_finalized_head_root_lookup_key() -> bytes:
        return b'v1:beacon:finalized-head-root'

    @staticmethod
    def make_justified_head_root_lookup_key() -> bytes:
        return b'v1:beacon:justified-head-root'

    @staticmethod
    def make_block_slot_to_root_lookup_key(slot: int) -> bytes:
        slot_to_root_key = b'v1:beacon:block-slot-to-root:%d' % slot
        return slot_to_root_key

    @staticmethod
    def make_block_root_to_score_lookup_key(block_root: Hash32) -> bytes:
        return b'v1:beacon:block-root-to-score:%s' % block_root

    @staticmethod
    def make_block_root_to_slot_lookup_key(block_root: Hash32) -> bytes:
        return b'v1:beacon:block-root-to-slot:%s' % block_root

    #
    # Attestaion
    #
    @staticmethod
    def make_attestation_root_to_block_lookup_key(attestaton_root: Hash32) -> bytes:
        return b'v1:beacon:attestation-root-to-block:%s' % attestaton_root
