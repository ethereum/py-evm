import time
from typing import (
    Any,
    Iterator,
    Optional,
    Tuple,
    Union,
    overload,
)

import rlp
from rlp.sedes import (
    big_endian_int,
    Binary,
    binary,
)

from cytoolz import (
    accumulate,
    sliding_window,
)
from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    to_dict,
)

from eth_hash.auto import keccak

from evm.constants import (
    ZERO_ADDRESS,
    ZERO_HASH32,
    EMPTY_UNCLE_HASH,
    GENESIS_NONCE,
    BLANK_ROOT_HASH,
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
    trie_root,
)

from evm.vm.execution_context import (
    ExecutionContext,
)


class MiningHeader(rlp.Serializable):
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
    ]


HeaderParams = Union[Optional[int], bytes, Address, Hash32]


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

    @overload
    def __init__(self, **kwargs: HeaderParams) -> None:
        ...

    @overload  # noqa: F811
    def __init__(self,
                 difficulty: int,
                 block_number: int,
                 gas_limit: int,
                 timestamp: int=None,
                 coinbase: Address=ZERO_ADDRESS,
                 parent_hash: Hash32=ZERO_HASH32,
                 uncles_hash: Hash32=EMPTY_UNCLE_HASH,
                 state_root: Hash32=BLANK_ROOT_HASH,
                 transaction_root: Hash32=BLANK_ROOT_HASH,
                 receipt_root: Hash32=BLANK_ROOT_HASH,
                 bloom: int=0,
                 gas_used: int=0,
                 extra_data: bytes=b'',
                 mix_hash: Hash32=ZERO_HASH32,
                 nonce: bytes=GENESIS_NONCE) -> None:
        ...

    def __init__(self,  # noqa: F811
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

    def __repr__(self) -> str:
        return '<BlockHeader #{0} {1}>'.format(
            self.block_number,
            encode_hex(self.hash)[2:10],
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = keccak(rlp.encode(self))
        return self._hash

    @property
    def mining_hash(self) -> Hash32:
        return keccak(rlp.encode(self[:-2], MiningHeader))

    @property
    def hex_hash(self):
        return encode_hex(self.hash)

    @classmethod
    def from_parent(cls,
                    parent: 'BlockHeader',
                    gas_limit: int,
                    difficulty: int,
                    timestamp: int,
                    coinbase: Address=ZERO_ADDRESS,
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


class CollationHeader(rlp.Serializable):
    """The header of a collation signed by the proposer."""

    fields_with_sizes = [
        ("shard_id", int32, 32),
        ("chunk_root", hash32, 32),
        ("period", int32, 32),
        ("proposer_address", address, 32),
    ]
    fields = [(name, sedes) for name, sedes, _ in fields_with_sizes]
    smc_encoded_size = sum(size for _, _, size in fields_with_sizes)

    def __repr__(self) -> str:
        return "<CollationHeader shard={} period={} hash={}>".format(
            self.shard_id,
            self.period,
            encode_hex(self.hash)[2:10],
        )

    @property
    def hash(self) -> Hash32:
        return keccak(self.encode_for_smc())

    def encode_for_smc(self) -> bytes:
        encoded = b"".join([
            int_to_bytes32(self.shard_id),
            self.chunk_root,
            int_to_bytes32(self.period),
            pad32(self.proposer_address),
        ])
        if len(encoded) != self.smc_encoded_size:
            raise ValueError("Encoded header size is {} instead of {} bytes".format(
                len(encoded),
                self.smc_encoded_size,
            ))
        return encoded

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
        for byte_range, field in zip(field_bounds, cls._meta.fields):
            start_index, end_index = byte_range
            field_name, field_type = field

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
