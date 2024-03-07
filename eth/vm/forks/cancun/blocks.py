from abc import (
    ABC,
)
from typing import (
    List,
    Type,
    cast,
)

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
)
from eth_utils import (
    encode_hex,
    keccak,
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
from eth.vm.forks.london.blocks import (
    LondonBlockHeader,
)

from ..london.receipts import (
    LondonReceiptBuilder,
)
from ..shanghai.blocks import (
    ShanghaiBackwardsHeader,
    ShanghaiBlock,
    ShanghaiBlockHeader,
)
from ..shanghai.withdrawals import (
    Withdrawal,
)
from .transactions import (
    CancunTransactionBuilder,
)


class CancunBlockHeader(rlp.Serializable, BlockHeaderAPI, ABC):
    fields = [
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
        ("mix_hash", binary),
        ("nonce", Binary(8, allow_empty=True)),
        ("base_fee_per_gas", big_endian_int),
        ("withdrawals_root", trie_root),
        # Cancun-specific fields:
        ("blob_gas_used", big_endian_int),
        ("excess_blob_gas", big_endian_int),
        ("parent_beacon_block_root", hash32),
    ]

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
        withdrawals_root: Hash32 = BLANK_ROOT_HASH,
        blob_gas_used: int = 0,
        excess_blob_gas: int = 0,
        parent_beacon_block_root: Hash32 = ZERO_HASH32,
    ) -> None:
        if timestamp is None:
            if parent_hash == ZERO_HASH32:
                timestamp = new_timestamp_from_parent(None)
            else:
                # without access to the parent header, we cannot select a new
                # timestamp correctly
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
            withdrawals_root=withdrawals_root,
            blob_gas_used=blob_gas_used,
            excess_blob_gas=excess_blob_gas,
            parent_beacon_block_root=parent_beacon_block_root,
        )

    def __str__(self) -> str:
        return f"<CancunBlockHeader #{self.block_number} {encode_hex(self.hash)[2:10]}>"

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = keccak(rlp.encode(self))
        return cast(Hash32, self._hash)

    @property
    def mining_hash(self) -> Hash32:
        raise ValueError("Mining hash is not available post merge.")

    @property
    def hex_hash(self) -> str:
        return encode_hex(self.hash)

    @property
    def is_genesis(self) -> bool:
        return self.parent_hash == GENESIS_PARENT_HASH and self.block_number == 0


class CancunBackwardsHeader(ShanghaiBackwardsHeader):
    """
    An rlp sedes class for block headers.
    It can serialize and deserialize Cancun, Shanghai, London, and pre-London headers.
    """

    @classmethod
    def deserialize(cls, encoded: List[bytes]) -> BlockHeaderAPI:
        num_fields = len(encoded)
        if num_fields == 20:
            return CancunBlockHeader.deserialize(encoded)
        if num_fields == 17:
            return ShanghaiBlockHeader.deserialize(encoded)
        if num_fields == 16:
            return LondonBlockHeader.deserialize(encoded)
        elif num_fields == 15:
            return BlockHeader.deserialize(encoded)
        else:
            raise ValueError(
                "Unexpected number of fields in block header."
                f"Got {num_fields} in {encoded!r}"
            )


class CancunBlock(ShanghaiBlock):
    transaction_builder: Type[TransactionBuilderAPI] = CancunTransactionBuilder
    receipt_builder: Type[ReceiptBuilderAPI] = LondonReceiptBuilder
    fields = [
        ("header", CancunBlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(None, max_length=0)),
        ("withdrawals", CountableList(Withdrawal)),
    ]
