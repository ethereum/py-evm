import time

import rlp
from rlp.sedes import (
    big_endian_int,
    Binary,
    binary,
)

from cytoolz import (
    first,
)
from eth_utils import (
    keccak,
    to_dict,
)

from evm.constants import (
    ZERO_ADDRESS,
    ZERO_HASH32,
    EMPTY_UNCLE_HASH,
    GENESIS_NONCE,
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
    SHARD_GAS_LIMIT,
)
from evm.exceptions import (
    ValidationError,
)

from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.numeric import (
    int_to_bytes32,
)
from evm.utils.padding import (
    pad32,
)

from .sedes import (
    address,
    hash32,
    int256,
    trie_root,
)

from evm.vm.execution_context import (
    ExecutionContext,
)


class BlockHeader(rlp.Serializable):
    fields = [
        ('parent_hash', hash32),
        ('uncles_hash', hash32),
        ('coinbase', address),
        ('state_root', trie_root),
        ('transaction_root', trie_root),
        ('receipt_root', trie_root),
        ('bloom', int256),
        ('difficulty', big_endian_int),
        ('block_number', big_endian_int),
        ('gas_limit', big_endian_int),
        ('gas_used', big_endian_int),
        ('timestamp', big_endian_int),
        ('extra_data', binary),
        ('mix_hash', binary),
        ('nonce', Binary(8, allow_empty=True))
    ]

    def __init__(self,
                 difficulty,
                 block_number,
                 gas_limit,
                 timestamp=None,
                 coinbase=ZERO_ADDRESS,
                 parent_hash=ZERO_HASH32,
                 uncles_hash=EMPTY_UNCLE_HASH,
                 state_root=BLANK_ROOT_HASH,
                 transaction_root=BLANK_ROOT_HASH,
                 receipt_root=BLANK_ROOT_HASH,
                 bloom=0,
                 gas_used=0,
                 extra_data=b'',
                 mix_hash=ZERO_HASH32,
                 nonce=GENESIS_NONCE):
        if timestamp is None:
            timestamp = int(time.time())
        super(BlockHeader, self).__init__(
            parent_hash=parent_hash,
            uncles_hash=uncles_hash,
            coinbase=coinbase,
            state_root=state_root,
            transaction_root=transaction_root,
            receipt_root=receipt_root,
            bloom=bloom,
            difficulty=difficulty,
            block_number=block_number,
            gas_limit=gas_limit,
            gas_used=gas_used,
            timestamp=timestamp,
            extra_data=extra_data,
            mix_hash=mix_hash,
            nonce=nonce,
        )

    def __repr__(self):
        return '<BlockHeader #{0} {1}>'.format(
            self.block_number,
            encode_hex(self.hash)[2:10],
        )

    @property
    def hash(self):
        return keccak(rlp.encode(self))

    @property
    def mining_hash(self):
        return keccak(
            rlp.encode(self, BlockHeader.exclude(['mix_hash', 'nonce'])))

    @property
    def hex_hash(self):
        return encode_hex(self.hash)

    @classmethod
    def from_parent(cls,
                    parent,
                    gas_limit,
                    difficulty,
                    timestamp,
                    coinbase=ZERO_ADDRESS,
                    nonce=None,
                    extra_data=None,
                    transaction_root=None,
                    receipt_root=None):
        """
        Initialize a new block header with the `parent` header as the block's
        parent hash.
        """
        header_kwargs = {
            'parent_hash': parent.hash,
            'coinbase': coinbase,
            'state_root': parent.state_root,
            'gas_limit': gas_limit,
            'difficulty': difficulty,
            'block_number': parent.block_number + 1,
            'timestamp': timestamp,
        }
        if nonce is not None:
            header_kwargs['nonce'] = nonce
        if extra_data is not None:
            header_kwargs['extra_data'] = extra_data
        if transaction_root is not None:
            header_kwargs['transaction_root'] = transaction_root
        if receipt_root is not None:
            header_kwargs['receipt_root'] = receipt_root

        header = cls(**header_kwargs)
        return header

    def clone(self):
        # Create a new BlockHeader object with the same fields.
        return self.__class__(**{
            field_name: getattr(self, field_name)
            for field_name
            in first(zip(*self.fields))
        })

    def create_execution_context(self, prev_hashes):
        return ExecutionContext(
            coinbase=self.coinbase,
            timestamp=self.timestamp,
            block_number=self.block_number,
            difficulty=self.difficulty,
            gas_limit=self.gas_limit,
            prev_hashes=prev_hashes,
        )


class CollationHeader(rlp.Serializable):
    fields = [
        ("shard_id", big_endian_int),
        ("expected_period_number", big_endian_int),
        ("period_start_prevhash", hash32),
        ("parent_hash", hash32),
        ("transaction_root", hash32),
        ("coinbase", address),
        ("state_root", hash32),
        ("receipt_root", hash32),
        ("number", big_endian_int),
    ]

    def __init__(self,
                 shard_id,
                 expected_period_number,
                 period_start_prevhash,
                 parent_hash,
                 number,
                 transaction_root=EMPTY_SHA3,
                 coinbase=ZERO_ADDRESS,
                 state_root=EMPTY_SHA3,
                 receipt_root=EMPTY_SHA3,
                 sig=b""):
        super(CollationHeader, self).__init__(
            shard_id=shard_id,
            expected_period_number=expected_period_number,
            period_start_prevhash=period_start_prevhash,
            parent_hash=parent_hash,
            transaction_root=transaction_root,
            coinbase=coinbase,
            state_root=state_root,
            receipt_root=receipt_root,
            number=number,
        )

    def __repr__(self):
        return "<CollationHeader #{0} {1} (shard #{2})>".format(
            self.expected_period_number,
            encode_hex(self.hash)[2:10],
            self.shard_id,
        )

    @property
    def hash(self):
        header_hash = keccak(
            b''.join((
                int_to_bytes32(self.shard_id),
                int_to_bytes32(self.expected_period_number),
                self.period_start_prevhash,
                self.parent_hash,
                self.transaction_root,
                pad32(self.coinbase),
                self.state_root,
                self.receipt_root,
                int_to_bytes32(self.number),
            ))
        )
        return header_hash

    @classmethod
    @to_dict
    def _deserialize_header_bytes_to_dict(cls, header_bytes):
        # assume all fields are padded to 32 bytes
        obj_size = 32
        if len(header_bytes) != obj_size * len(cls.fields):
            raise ValidationError(
                "Expected header bytes to be of length: {0}. Got length {1} instead.\n- {2}".format(
                    obj_size * len(cls.fields),
                    len(header_bytes),
                    encode_hex(header_bytes),
                )
            )
        for idx, field in enumerate(cls.fields):
            field_name, field_type = field
            start_index = idx * obj_size
            field_bytes = header_bytes[start_index:(start_index + obj_size)]
            if field_type == rlp.sedes.big_endian_int:
                # remove the leading zeros, to avoid `not minimal length` error in deserialization
                formatted_field_bytes = field_bytes.lstrip(b'\x00')
            elif field_type == address:
                formatted_field_bytes = field_bytes[-20:]
            else:
                formatted_field_bytes = field_bytes
            yield field_name, field_type.deserialize(formatted_field_bytes)

    @classmethod
    def from_bytes(cls, header_bytes):
        header_kwargs = cls._deserialize_header_bytes_to_dict(header_bytes)
        header = cls(**header_kwargs)
        return header

    @classmethod
    def from_parent(cls,
                    parent,
                    period_start_prevhash,
                    expected_period_number,
                    coinbase=ZERO_ADDRESS):
        """
        Initialize a new collation header with the `parent` header as the collation's
        parent hash.
        """
        header_kwargs = {
            "shard_id": parent.shard_id,
            "expected_period_number": expected_period_number,
            "period_start_prevhash": period_start_prevhash,
            "parent_hash": parent.hash,
            "state_root": parent.state_root,
            "number": parent.number + 1,
        }
        header = cls(**header_kwargs)
        return header

    def clone(self):
        # Create a new CollationHeader object with the same fields.
        return self.__class__(**{
            field_name: getattr(self, field_name)
            for field_name
            in first(zip(*self.fields))
        })

    def create_execution_context(self, prev_hashes):
        return ExecutionContext(
            coinbase=self.coinbase,
            timestamp=None,
            block_number=self.number,
            difficulty=None,
            gas_limit=SHARD_GAS_LIMIT,
            prev_hashes=prev_hashes,
        )
