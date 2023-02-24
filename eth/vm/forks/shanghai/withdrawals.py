from cached_property import cached_property
from typing import cast

from eth.abc import WithdrawalAPI
from eth_typing import Address, Hash32

import rlp
from eth.rlp.sedes import address
from eth_utils import keccak


class Withdrawal(rlp.Serializable):
    fields = [
        ('index', rlp.sedes.big_endian_int),
        ('validator_index', rlp.sedes.big_endian_int),
        ('address', address),
        ('amount', rlp.sedes.big_endian_int),
    ]

    def __init__(
        self,
        index: int = 0,
        validator_index: int = None,
        address: Address = None,
        amount: int = 0,
    ) -> None:
        super().__init__(
            index=index,
            validator_index=validator_index,
            address=address,
            amount=amount,
        )

    @classmethod
    def decode(cls, encoded: bytes) -> WithdrawalAPI:
        return rlp.decode(encoded, sedes=cls)

    def encode(self) -> bytes:
        return rlp.encode(self)

    @cached_property
    def hash(self) -> Hash32:
        return cast(Hash32, keccak(self.encode()))
