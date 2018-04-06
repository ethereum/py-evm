import time

import rlp
from rlp.sedes import (
    big_endian_int,
    Binary,
    binary,
)

from cytoolz import (
    accumulate,
    first,
    sliding_window,
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
    int32,
    int256,
    proposer_signature,
    trie_root,
)

from evm.vm.execution_context import (
    ExecutionContext,
)

from typing import (
    Any,
    Iterator,
    Tuple,
    Union,
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
                 difficulty: int,
                 block_number: int,
                 gas_limit: int,
                 timestamp: int=None,
                 coinbase: bytes=ZERO_ADDRESS,
                 parent_hash: bytes=ZERO_HASH32,
                 uncles_hash: bytes=EMPTY_UNCLE_HASH,
                 state_root: bytes=BLANK_ROOT_HASH,
                 transaction_root: bytes=BLANK_ROOT_HASH,
                 receipt_root: bytes=BLANK_ROOT_HASH,
                 bloom: int=0,
                 gas_used: int=0,
                 extra_data: bytes=b'',
                 mix_hash: bytes=ZERO_HASH32,
                 nonce: bytes=GENESIS_NONCE) -> None:
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

    def __repr__(self) -> str:
        return '<BlockHeader #{0} {1}>'.format(
            self.block_number,
            encode_hex(self.hash)[2:10],
        )

    @property
    def hash(self) -> bytes:
        return keccak(rlp.encode(self))

    @property
    def mining_hash(self) -> bytes:
        return keccak(
            rlp.encode(self, BlockHeader.exclude(['mix_hash', 'nonce'])))

    @property
    def hex_hash(self):
        return encode_hex(self.hash)

    @classmethod
    def from_parent(cls,
                    parent: 'BlockHeader',
                    gas_limit: int,
                    difficulty: int,
                    timestamp: int,
                    coinbase: bytes=ZERO_ADDRESS,
                    nonce: bytes=None,
                    extra_data: bytes=None,
                    transaction_root: bytes=None,
                    receipt_root: bytes=None) -> 'BlockHeader':
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

    def clone(self) -> 'BlockHeader':
        # Create a new BlockHeader object with the same fields.
        return self.__class__(**{
            field_name: getattr(self, field_name)
            for field_name
            in first(zip(*self.fields))
        })

    def create_execution_context(
            self, prev_hashes: Union[Tuple[bytes], Tuple[bytes, bytes]]) -> ExecutionContext:

        return ExecutionContext(
            coinbase=self.coinbase,
            timestamp=self.timestamp,
            block_number=self.block_number,
            difficulty=self.difficulty,
            gas_limit=self.gas_limit,
            prev_hashes=prev_hashes,
        )


class UnsignedCollationHeader(rlp.Serializable):
    fields = [
        ("shard_id", big_endian_int),
        ("expected_period_number", big_endian_int),
        ("period_start_prevhash", hash32),
        ("parent_hash", hash32),
        ("chunk_root", hash32),
        ("period", int32),
        ("height", int32),
        ("proposer_address", address),
        ("proposer_bid", int32),
    ]

    def __init__(self,
                 shard_id: int,
                 expected_period_number: int,
                 period_start_prevhash: bytes,
                 parent_hash: bytes,
                 number: int,
                 transaction_root: bytes=EMPTY_SHA3,
                 coinbase: bytes=ZERO_ADDRESS,
                 state_root: bytes=EMPTY_SHA3,
                 receipt_root: bytes=EMPTY_SHA3,
                 sig: bytes=b'') -> None:
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

    def __repr__(self) -> str:
        return "<UnsignedCollationHeader {} shard={} height={}>".format(
            encode_hex(self.hash)[2:10],
            self.shard_id,
            self.height,
        )

    @classmethod
    def from_parent(
        cls,
        parent: 'CollationHeader',
        chunk_root: bytes,
        period: int,
        proposer_address: bytes,
        proposer_bid: int,
    ) -> "UnsignedCollationHeader":
        """Initialize a new unsigned collation header as a child from another header."""
        header_kwargs = {
            "shard_id": parent.shard_id,
            "parent_hash": parent.hash,
            "chunk_root": chunk_root,
            "period": period,
            "height": parent.height + 1,
            "proposer_address": proposer_address,
            "proposer_bid": proposer_bid,
        }
        return cls(**header_kwargs)

    @property
    def hash(self) -> bytes:
        """Calculate the hash used to create the proposer signature."""
        header_hash = keccak(
            b''.join([
                int_to_bytes32(self.shard_id),
                int_to_bytes32(self.expected_period_number),
                self.period_start_prevhash,
                self.parent_hash,
                self.chunk_root,
                int_to_bytes32(self.period),
                int_to_bytes32(self.height),
                pad32(self.proposer_address),
                int_to_bytes32(self.proposer_bid),
            ])
        )
        # Hash of Collation header is the right most 26 bytes of `sha3(header)`
        # It's padded to 32 bytes because `bytes32` is easier to handle in Vyper
        return pad32(header_hash[6:])

    def to_signed_collation(self) -> "CollationHeader":
        raise NotImplementedError("TODO")


class CollationHeader(rlp.Serializable):
    """The header of a collation signed by the proposer."""

    fields_with_sizes = [
        ("shard_id", int32, 32),
        ("parent_hash", hash32, 32),
        ("chunk_root", hash32, 32),
        ("period", int32, 32),
        ("height", int32, 32),
        ("proposer_address", address, 32),
        ("proposer_bid", int32, 32),
        ("proposer_signature", proposer_signature, 96),
    ]
    fields = [(name, sedes) for name, sedes, _ in fields_with_sizes]
    smc_encoded_size = sum(size for _, _, size in fields_with_sizes)

    def __repr__(self) -> str:
        return "<CollationHeader {} shard={} height={}>".format(
            encode_hex(self.hash)[2:10],
            self.shard_id,
            self.height,
        )

    def encode_for_smc(self) -> bytes:
        encoded = b"".join([
            int_to_bytes32(self.shard_id),
            self.parent_hash,
            self.chunk_root,
            int_to_bytes32(self.period),
            int_to_bytes32(self.height),
            pad32(self.proposer_address),
            int_to_bytes32(self.proposer_bid),
            self.proposer_signature,
        ])
        assert len(encoded) == self.smc_encoded_size
        return encoded

    @property
    def hash(self) -> bytes:
        return keccak(self.encode_for_smc())

    @classmethod
    @to_dict
    def _decode_header_to_dict(cls, encoded_header: bytes) -> Iterator[Tuple[str, Any]]:
        if len(encoded_header) != cls.smc_encoded_size:
            raise ValidationError(
                "Expected encoded header to be of size: {0}. Got size {1} instead.\n- {2}".format(
                    cls.smc_encoded_size,
                    len(encoded_header),
                    encode_hex(encoded_header),
                )
            )

        start_indices = accumulate(lambda i, field: i + field[2], cls.fields_with_sizes, 0)
        field_bounds = sliding_window(2, start_indices)
        for (start_index, end_index), (field_name, field_type) in zip(field_bounds, cls.fields):
            field_bytes = encoded_header[start_index:end_index]
            if field_type == rlp.sedes.big_endian_int:
                # remove the leading zeros, to avoid `not minimal length` error in deserialization
                formatted_field_bytes = field_bytes.lstrip(b'\x00')
            elif field_type == address:
                formatted_field_bytes = field_bytes[-20:]
            else:
                formatted_field_bytes = field_bytes
            yield field_name, field_type.deserialize(formatted_field_bytes)

    @classmethod
    def decode_from_smc(cls, encoded_header: bytes) -> "CollationHeader":
        header_kwargs = cls._decode_header_to_dict(encoded_header)
        header = cls(**header_kwargs)
        return header

    @property
    def is_genesis(self) -> bool:
        return self.height == 0
