from cached_property import cached_property
from typing import cast

from eth.abc import WithdrawalAPI
from eth.validation import (
    validate_canonical_address,
    validate_uint64,
)
from eth_typing import (
    Address,
    Hash32,
)

import rlp
from eth.rlp.sedes import address
from eth_utils import keccak
from rlp.sedes import big_endian_int


class Withdrawal(rlp.Serializable):
    fields = [
        ('index', big_endian_int),
        ('validator_index', big_endian_int),
        ('address', address),
        ('amount', big_endian_int),
    ]

    def __init__(
        self,
        index: int = 0,
        validator_index: int = 0,
        address: Address = None,
        amount: int = 0,
    ) -> None:
        super().__init__(
            index=index,
            validator_index=validator_index,
            address=address,
            amount=amount,
        )

    def validate(self) -> None:
        validate_uint64(self.index, "Withdrawal.index")
        validate_uint64(self.validator_index, "Withdrawal.validator_index")
        validate_canonical_address(self.address, "Withdrawal.address")
        validate_uint64(self.amount, "Withdrawal.amount")

    @classmethod
    def decode(cls, encoded: bytes) -> WithdrawalAPI:
        return rlp.decode(encoded, sedes=cls)

    def encode(self) -> bytes:
        return rlp.encode(self)

    @cached_property
    def hash(self) -> Hash32:
        return cast(Hash32, keccak(self.encode()))
