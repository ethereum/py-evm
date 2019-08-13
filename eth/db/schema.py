from abc import ABC, abstractmethod
from enum import Enum

from eth.exceptions import (
    SchemaDoesNotMatchError,
    SchemaNotRecognizedError,
)

from eth.db.backends.base import BaseDB

from eth_typing import (
    BlockNumber,
    Hash32,
)


class Schemas(Enum):
    DEFAULT = b'default'
    TURBO = b'turbo'


class BaseSchema(ABC):
    @staticmethod
    @abstractmethod
    def make_canonical_head_hash_lookup_key() -> bytes:
        raise NotImplementedError('Must be implemented by subclasses')

    @staticmethod
    @abstractmethod
    def make_block_number_to_hash_lookup_key(block_number: BlockNumber) -> bytes:
        raise NotImplementedError('Must be implemented by subclasses')

    @staticmethod
    @abstractmethod
    def make_block_hash_to_score_lookup_key(block_hash: Hash32) -> bytes:
        raise NotImplementedError('Must be implemented by subclasses')

    @staticmethod
    @abstractmethod
    def make_transaction_hash_to_block_lookup_key(transaction_hash: Hash32) -> bytes:
        raise NotImplementedError('Must be implemented by subclasses')


class SchemaV1(BaseSchema):
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


class SchemaTurbo(SchemaV1):
    current_schema_lookup_key: bytes = b'current-schema'
    _block_diff_prefix = b'block-diff'

    # TODO: this naming is terrible, what should the name be?
    current_state_lookup_key: bytes = b'current-turbo-state'

    @classmethod
    def make_block_diff_lookup_key(cls, block_hash: Hash32) -> bytes:
        return cls._block_diff_prefix + b':' + block_hash

    @classmethod
    def make_account_state_lookup_key(cls, address_hash: Hash32) -> bytes:
        return cls.current_state_lookup_key + b':' + address_hash


def get_schema(db: BaseDB) -> Schemas:
    try:
        current_schema = db[SchemaTurbo.current_schema_lookup_key]
    except KeyError:
        return Schemas.DEFAULT

    try:
        return Schemas(current_schema)
    except ValueError:
        raise SchemaNotRecognizedError(current_schema)


def set_schema(db: BaseDB, schema: Schemas) -> None:
    db.set(SchemaTurbo.current_schema_lookup_key, schema.value)


def ensure_schema(db: BaseDB, expected_schema: Schemas) -> None:
    reported_schema = get_schema(db)
    if reported_schema != expected_schema:
        raise SchemaDoesNotMatchError(reported_schema)
