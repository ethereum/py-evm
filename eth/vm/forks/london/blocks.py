import time

from typing import (
    Dict,
    Optional,
    Type,
    overload,
)
from eth_utils.exceptions import ValidationError

import rlp

from rlp.sedes import (
    Binary,
    CountableList,
    big_endian_int,
    binary
)

from eth.abc import (
    BlockHeaderAPI,
    MiningHeaderAPI,
    ReceiptBuilderAPI,
    TransactionBuilderAPI,
)
from eth.constants import (
    ZERO_ADDRESS,
    ZERO_HASH32,
    EMPTY_UNCLE_HASH,
    GENESIS_NONCE,
    GENESIS_PARENT_HASH,
    BLANK_ROOT_HASH,
)
from eth.rlp.sedes import (
    address,
    hash32,
    trie_root,
    uint256,
)
from eth.typing import HeaderParams
from eth.vm.forks.berlin.blocks import (
    BerlinBlock,
)
from eth_hash.auto import keccak

from eth_typing import (
    BlockNumber,
)
from eth_typing.evm import (
    Address,
    Hash32
)
from eth_utils import (
    encode_hex,
)

from .receipts import (
    LondonReceiptBuilder,
)
from .transactions import (
    LondonTransactionBuilder,
)


class LondonMiningHeader(rlp.Serializable, MiningHeaderAPI):
    fields = [
        ('parent_hash', hash32),
        ('uncles_hash', hash32),
        ('coinbase', address),
        ('state_root', trie_root),
        ('transaction_root', trie_root),
        ('receipt_root', trie_root),
        ('bloom', uint256),
        ('difficulty', big_endian_int),
        ('block_number', big_endian_int),
        ('gas_limit', big_endian_int),
        ('gas_used', big_endian_int),
        ('timestamp', big_endian_int),
        ('extra_data', binary),
        ('base_fee_per_gas', big_endian_int),
    ]


class LondonBlockHeader(rlp.Serializable, BlockHeaderAPI):
    fields = [
        ('parent_hash', hash32),
        ('uncles_hash', hash32),
        ('coinbase', address),
        ('state_root', trie_root),
        ('transaction_root', trie_root),
        ('receipt_root', trie_root),
        ('bloom', uint256),
        ('difficulty', big_endian_int),
        ('block_number', big_endian_int),
        ('gas_limit', big_endian_int),
        ('gas_used', big_endian_int),
        ('timestamp', big_endian_int),
        ('extra_data', binary),
        ('base_fee_per_gas', big_endian_int),
        ('mix_hash', binary),
        ('nonce', Binary(8, allow_empty=True)),
    ]
    def __init__(self,              # type: ignore  # noqa: F811
                 difficulty: int,
                 block_number: BlockNumber,
                 gas_limit: int,
                 timestamp: int = None,
                 coinbase: Address = ZERO_ADDRESS,
                 parent_hash: Hash32 = ZERO_HASH32,
                 uncles_hash: Hash32 = EMPTY_UNCLE_HASH,
                 state_root: Hash32 = BLANK_ROOT_HASH,
                 transaction_root: Hash32 = BLANK_ROOT_HASH,
                 receipt_root: Hash32 = BLANK_ROOT_HASH,
                 bloom: int = 0,
                 gas_used: int = 0,
                 extra_data: bytes = b'',
                 mix_hash: Hash32 = ZERO_HASH32,
                 nonce: bytes = GENESIS_NONCE,
                 base_fee_per_gas: int = 0) -> None:
        if timestamp is None:
            timestamp = int(time.time())
        super().__init__(
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
            base_fee_per_gas=base_fee_per_gas,
        )

    def __str__(self) -> str:
        return f'<BlockHeader #{self.block_number} {encode_hex(self.hash)[2:10]}>'

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = keccak(rlp.encode(self))
        return self._hash

    @property
    def mining_hash(self) -> Hash32:
        return keccak(rlp.encode(self[:-2], LondonMiningHeader))

    @property
    def hex_hash(self) -> str:
        return encode_hex(self.hash)

    @classmethod
    def from_parent(cls,
                    parent: 'BlockHeaderAPI',
                    difficulty: int,
                    timestamp: int,
                    gas_limit: int,
                    coinbase: Address = ZERO_ADDRESS,
                    base_fee_per_gas: int = 0,  # TODO is this correct?
                    nonce: bytes = None,
                    extra_data: bytes = None,
                    transaction_root: bytes = None,
                    receipt_root: bytes = None) -> 'BlockHeaderAPI':
        """
        Initialize a new block header with the `parent` header as the block's
        parent hash.
        """
        header_kwargs: Dict[str, HeaderParams] = {
            'parent_hash': parent.hash,
            'coinbase': coinbase,
            'state_root': parent.state_root,
            'gas_limit': gas_limit,
            'base_fee_per_gas': base_fee_per_gas,
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

        header = cls(**header_kwargs)  # type: ignore
        return header

    @property
    def is_genesis(self) -> bool:
        # if removing the block_number == 0 test, consider the validation consequences.
        # validate_header stops trying to check the current header against a parent header.
        # Can someone trick us into following a high difficulty header with genesis parent hash?
        return self.parent_hash == GENESIS_PARENT_HASH and self.block_number == 0


class LondonBlock(BerlinBlock):
    transaction_builder: Type[TransactionBuilderAPI] = LondonTransactionBuilder  # type: ignore
    receipt_builder: Type[ReceiptBuilderAPI] = LondonReceiptBuilder  # type: ignore
    fields = [
        ('header', LondonBlockHeader),
        ('transactions', CountableList(transaction_builder)),
        ('uncles', CountableList(LondonBlockHeader))
    ]
