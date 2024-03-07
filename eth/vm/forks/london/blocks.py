from typing import (
    List,
    Optional,
    Type,
    cast,
)

from eth_hash.auto import (
    keccak,
)
from eth_typing import (
    BlockNumber,
)
from eth_typing.evm import (
    Address,
    Hash32,
)
from eth_utils import (
    encode_hex,
)
import rlp
from rlp.sedes import (
    Binary,
    CountableList,
    big_endian_int,
    binary,
)

from eth._utils.headers import (
    new_timestamp_from_parent,
)
from eth.abc import (
    BlockHeaderAPI,
    BlockHeaderSedesAPI,
    MiningHeaderAPI,
    ReceiptBuilderAPI,
    TransactionBuilderAPI,
)
from eth.constants import (
    BLANK_ROOT_HASH,
    EMPTY_UNCLE_HASH,
    GENESIS_NONCE,
    GENESIS_PARENT_HASH,
    ZERO_ADDRESS,
    ZERO_HASH32,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.rlp.sedes import (
    address,
    hash32,
    trie_root,
    uint256,
)
from eth.vm.forks.berlin.blocks import (
    BerlinBlock,
)

from .receipts import (
    LondonReceiptBuilder,
)
from .transactions import (
    LondonTransactionBuilder,
)

UNMINED_LONDON_HEADER_FIELDS = [
    ("parent_hash", hash32),
    ("uncles_hash", hash32),
    ("coinbase", address),
    ("state_root", trie_root),
    ("transaction_root", trie_root),
    ("receipt_root", trie_root),
    ("bloom", uint256),
    ("difficulty", big_endian_int),
    ("block_number", big_endian_int),
    ("gas_limit", big_endian_int),
    ("gas_used", big_endian_int),
    ("timestamp", big_endian_int),
    ("extra_data", binary),
    ("base_fee_per_gas", big_endian_int),
]


class LondonMiningHeader(rlp.Serializable, MiningHeaderAPI):
    fields = UNMINED_LONDON_HEADER_FIELDS


class LondonBlockHeader(rlp.Serializable, BlockHeaderAPI):
    fields = (
        UNMINED_LONDON_HEADER_FIELDS[:-1]
        + [
            ("mix_hash", binary),
            ("nonce", Binary(8, allow_empty=True)),
        ]
        + UNMINED_LONDON_HEADER_FIELDS[-1:]
    )

    def __init__(
        self,
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
        extra_data: bytes = b"",
        mix_hash: Hash32 = ZERO_HASH32,
        nonce: bytes = GENESIS_NONCE,
        base_fee_per_gas: int = 0,
    ) -> None:
        if timestamp is None:
            if parent_hash == ZERO_HASH32:
                timestamp = new_timestamp_from_parent(None)
            else:
                # without access to the parent header,
                # we cannot select a new timestamp correctly
                raise ValueError(
                    "Must set timestamp explicitly if this is not a genesis header"
                )
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
        return f"<LondonBlockHeader #{self.block_number} {encode_hex(self.hash)[2:10]}>"

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = keccak(rlp.encode(self))
        return cast(Hash32, self._hash)

    @property
    def mining_hash(self) -> Hash32:
        non_pow_fields = self[:-3] + self[-1:]
        result = keccak(rlp.encode(non_pow_fields, LondonMiningHeader))
        return cast(Hash32, result)

    @property
    def hex_hash(self) -> str:
        return encode_hex(self.hash)

    @property
    def is_genesis(self) -> bool:
        # if removing the block_number == 0 test, consider the validation consequences.
        # validate_header stops trying to check the current header against
        # a parent header. Can someone trick us into following a high difficulty header
        # with genesis parent hash?
        return self.parent_hash == GENESIS_PARENT_HASH and self.block_number == 0

    @property
    def withdrawals_root(self) -> Optional[Hash32]:
        raise AttributeError("Withdrawals root not available until Shanghai fork")

    @property
    def blob_gas_used(self) -> int:
        raise AttributeError("Blob gas used not available until Cancun fork")

    @property
    def excess_blob_gas(self) -> int:
        raise AttributeError("Excess blob gas not available until Cancun fork")

    @property
    def parent_beacon_block_root(self) -> Optional[Hash32]:
        raise AttributeError("Parent beacon block root not available until Cancun fork")


class LondonBackwardsHeader(BlockHeaderSedesAPI):
    """
    An rlp sedes class for block headers.

    It can serialize and deserialize *both* London and pre-London headers.
    """

    @classmethod
    def serialize(cls, obj: BlockHeaderAPI) -> List[bytes]:
        return obj.serialize(obj)

    @classmethod
    def deserialize(cls, encoded: List[bytes]) -> BlockHeaderAPI:
        num_fields = len(encoded)
        if num_fields == 16:
            return LondonBlockHeader.deserialize(encoded)
        elif num_fields == 15:
            return BlockHeader.deserialize(encoded)
        else:
            raise ValueError(
                "London & earlier can only handle headers of 15 or 16 fields. "
                f"Got {num_fields} in {encoded!r}"
            )


class LondonBlock(BerlinBlock):
    transaction_builder: Type[TransactionBuilderAPI] = LondonTransactionBuilder
    receipt_builder: Type[ReceiptBuilderAPI] = LondonReceiptBuilder
    fields = [
        ("header", LondonBlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(LondonBackwardsHeader)),
    ]
